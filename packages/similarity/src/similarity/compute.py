"""Species x side centroids, their nearest images, and the ranked similar species.

Strategy (optimized for speed):
  1. Group images by species + side and compute centroids in bulk.
  2. Batch matrix multiplication (numpy BLAS) for cosine similarity, which
     parallelizes across all CPU cores automatically.
  3. For each centroid, pick the top-K nearest images and deduplicate by species.
"""

from __future__ import annotations

import logging
import time

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

SIDES = ("dorsal", "ventral")
# Batch size for matrix multiply (controls peak memory: batch_size * n_images * 4 bytes)
BATCH_SIZE = 200


def normalize_species(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def compute_centroids(
    meta: pl.DataFrame,
    embeddings: np.ndarray,
    img_ids: np.ndarray,
    species_filter: str | None = None,
) -> tuple[list[tuple[str, str]], np.ndarray]:
    """Compute normalized centroids for each (species, side) group.

    Returns:
        keys: list of (species, side) tuples
        centroids: (M, D) normalized float32 array
    """
    logger.info("Computing centroids...")
    t0 = time.time()

    id_to_idx = {img_id: i for i, img_id in enumerate(img_ids)}

    if species_filter:
        meta = meta.filter(pl.col("species") == species_filter)

    groups = meta.group_by(["species", "side"]).agg(pl.col("img_id"))

    keys = []
    centroid_list = []

    for row in groups.iter_rows(named=True):
        species = row["species"]
        side = row["side"]
        if side not in SIDES:
            continue

        indices = [id_to_idx[iid] for iid in row["img_id"] if iid in id_to_idx]
        if not indices:
            continue

        # Mean of normalized embeddings, then re-normalize
        centroid = embeddings[indices].mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid /= norm

        keys.append((species, side))
        centroid_list.append(centroid)

    centroids = np.array(centroid_list, dtype=np.float32)
    logger.info(f"Computed {len(keys)} centroids in {time.time() - t0:.1f}s")
    return keys, centroids


def batch_similarity_search(
    centroids: np.ndarray,
    embeddings: np.ndarray,
    top_k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the top-K most similar images for each centroid using batch matmul.

    Since both are L2-normalized, dot product = cosine similarity.
    Distance = 1 - similarity (so lower = more similar).

    Returns:
        top_indices: (M, top_k) int array of image indices
        top_distances: (M, top_k) float array of cosine distances
    """
    logger.info(
        f"Running batch similarity search "
        f"({len(centroids)} centroids × {len(embeddings)} images)..."
    )
    t0 = time.time()

    n_centroids = len(centroids)
    actual_top_k = min(top_k, len(embeddings))
    top_indices = np.empty((n_centroids, actual_top_k), dtype=np.int64)
    top_distances = np.empty((n_centroids, actual_top_k), dtype=np.float32)

    for start in range(0, n_centroids, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n_centroids)
        # Shape: (batch_size, n_images)
        distances = 1.0 - centroids[start:end] @ embeddings.T

        if actual_top_k < distances.shape[1]:
            # argpartition for an O(n) partial sort, then sort only the top-K
            part_idx = np.argpartition(distances, actual_top_k, axis=1)[:, :actual_top_k]
            batch_dists = np.take_along_axis(distances, part_idx, axis=1)
            sort_idx = np.argsort(batch_dists, axis=1)
            top_indices[start:end] = np.take_along_axis(part_idx, sort_idx, axis=1)
            top_distances[start:end] = np.take_along_axis(batch_dists, sort_idx, axis=1)
        else:
            sort_idx = np.argsort(distances, axis=1)
            top_indices[start:end] = sort_idx
            top_distances[start:end] = np.take_along_axis(distances, sort_idx, axis=1)

        if (start // BATCH_SIZE) % 10 == 0 and start > 0:
            elapsed = time.time() - t0
            progress = end / n_centroids
            eta = elapsed / progress * (1 - progress)
            logger.info(
                f"  Similarity search: {end}/{n_centroids} ({progress * 100:.0f}%), ETA {eta:.0f}s"
            )

    logger.info(f"Similarity search completed in {time.time() - t0:.1f}s")
    return top_indices, top_distances


def build_results(
    keys: list[tuple[str, str]],
    top_indices: np.ndarray,
    top_distances: np.ndarray,
    img_ids: np.ndarray,
    meta: pl.DataFrame,
    limit: int,
) -> pl.DataFrame:
    """Keep the nearest image of each other species, up to `limit` per centroid."""
    logger.info("Building final results...")
    t0 = time.time()

    img_species_map = dict(zip(meta["img_id"].to_list(), meta["species"].to_list(), strict=True))

    all_rows = []
    for i, (query_species, side) in enumerate(keys):
        seen_species = set()
        rank = 0

        for j in range(top_indices.shape[1]):
            img_id = img_ids[top_indices[i, j]]
            similar_species = img_species_map.get(img_id)
            # Images with no metadata row (for example an excluded family)
            if similar_species is None:
                continue

            normalized_similar = similar_species.lower().replace(" ", "_")
            if normalized_similar == query_species or normalized_similar in seen_species:
                continue

            seen_species.add(normalized_similar)
            rank += 1
            all_rows.append(
                {
                    "species": query_species,
                    "side": side,
                    "similar_species": similar_species,
                    "img_id": img_id,
                    "distance": float(top_distances[i, j]),
                    "rank": rank,
                }
            )
            if rank >= limit:
                break

    result_df = pl.DataFrame(
        all_rows,
        schema={
            "species": pl.String,
            "side": pl.String,
            "similar_species": pl.String,
            "img_id": pl.String,
            "distance": pl.Float64,
            "rank": pl.Int32,
        },
    )
    logger.info(f"Built {len(result_df)} result rows in {time.time() - t0:.1f}s")
    return result_df
