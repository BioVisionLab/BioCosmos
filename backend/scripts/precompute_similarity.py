#!/usr/bin/env python3
"""
Precompute per-species visual similarity and store results in DuckDB.

Strategy (optimized for speed):
  1. Load ALL embeddings + metadata into memory once
  2. Group images by species+side, compute centroids in bulk
  3. Use batch matrix multiplication (numpy BLAS) for cosine similarity
     — this parallelizes across all CPU cores automatically
  4. For each centroid, pick top-K nearest images, deduplicate by species
  5. Bulk insert all results into DuckDB

Usage:
    cd backend
    python scripts/precompute_similarity.py \
        --lance-dir lance_db_lite --duck-dir duck_db

    # Single species test:
    python scripts/precompute_similarity.py \
        --lance-dir lance_db_lite --duck-dir duck_db --species "vanessa_cardui"

    # Force recreate:
    python scripts/precompute_similarity.py \
        --lance-dir lance_db_lite --duck-dir duck_db --force
"""

import argparse
import logging
import os
import sys
import time

import duckdb
import lancedb
import numpy as np
import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Defaults
DEFAULT_LANCE_FILE = "biocosmos.lance"
DEFAULT_DUCK_FILE = "biocosmos.duckdb"
DEFAULT_LANCE_TABLE = "nymphalidae"
DEFAULT_META_TABLE = "image_meta"
DEFAULT_SIMILARITY_TABLE = "species_similarity"
DEFAULT_TOP_K = 800
DEFAULT_LIMIT = 10
SIDES = ["dorsal", "ventral"]
# Batch size for matrix multiply (controls peak memory: batch_size * n_images * 4 bytes)
BATCH_SIZE = 200


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precompute per-species visual similarity (optimized)."
    )
    parser.add_argument("--lance-dir", default="lance_db_lite")
    parser.add_argument("--duck-dir", default="duck_db")
    parser.add_argument("--lance-file", default=DEFAULT_LANCE_FILE)
    parser.add_argument("--duck-file", default=DEFAULT_DUCK_FILE)
    parser.add_argument("--lance-table", default=DEFAULT_LANCE_TABLE)
    parser.add_argument("--meta-table", default=DEFAULT_META_TABLE)
    parser.add_argument("--similarity-table", default=DEFAULT_SIMILARITY_TABLE)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help="Neighbors to fetch per centroid before dedup")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="Final unique species per side")
    parser.add_argument("--force", action="store_true",
                        help="Drop and recreate the similarity table")
    parser.add_argument("--species", type=str, default=None,
                        help="Compute for a single species (for testing)")
    return parser.parse_args()


def load_all_embeddings(lance_table) -> tuple[np.ndarray, np.ndarray]:
    """Load all UNICOM embeddings and img_ids from LanceDB into memory.

    Returns:
        embeddings: (N, 768) float32 array, L2-normalized
        img_ids: (N,) array of image ID strings
    """
    logger.info("Loading all embeddings into memory...")
    t0 = time.time()

    df = lance_table.to_polars().select(["img_id", "unicom_embeddings"]).collect()
    img_ids = df["img_id"].to_numpy()
    embeddings = np.array(df["unicom_embeddings"].to_list(), dtype=np.float32)

    # L2-normalize for cosine similarity via dot product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # avoid division by zero
    embeddings = embeddings / norms

    logger.info(
        f"Loaded {len(img_ids)} embeddings ({embeddings.nbytes / 1e9:.2f} GB) "
        f"in {time.time() - t0:.1f}s"
    )
    return embeddings, img_ids


def load_metadata(duck_conn, meta_table: str) -> pl.DataFrame:
    """Load image metadata (img_id, species, class_dv) into a Polars DataFrame."""
    logger.info("Loading image metadata...")
    meta = duck_conn.execute(f"""
        SELECT img_id,
               REPLACE(LOWER(species), ' ', '_') AS species,
               LOWER(class_dv) AS side
        FROM {meta_table}
    """).pl()
    logger.info(f"Loaded {len(meta)} metadata rows")
    return meta


def compute_centroids(
    meta: pl.DataFrame,
    embeddings: np.ndarray,
    img_ids: np.ndarray,
    species_filter: str | None = None,
) -> tuple[list[tuple[str, str]], np.ndarray]:
    """Compute normalized centroids for each (species, side) group.

    Returns:
        keys: list of (species, side) tuples
        centroids: (M, 768) normalized float32 array
    """
    logger.info("Computing centroids...")
    t0 = time.time()

    # Build img_id -> index lookup
    id_to_idx = {img_id: i for i, img_id in enumerate(img_ids)}

    # Filter metadata to only species we want
    if species_filter:
        meta = meta.filter(pl.col("species") == species_filter)

    # Group by species + side
    groups = meta.group_by(["species", "side"]).agg(pl.col("img_id"))

    keys = []
    centroid_list = []

    for row in groups.iter_rows(named=True):
        species = row["species"]
        side = row["side"]
        group_img_ids = row["img_id"]

        if side not in SIDES:
            continue

        # Get indices for this group's images
        indices = [id_to_idx[iid] for iid in group_img_ids if iid in id_to_idx]
        if not indices:
            continue

        # Compute centroid (mean of normalized embeddings, then re-normalize)
        centroid = embeddings[indices].mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid /= norm

        keys.append((species, side))
        centroid_list.append(centroid)

    centroids = np.array(centroid_list, dtype=np.float32)
    logger.info(
        f"Computed {len(keys)} centroids in {time.time() - t0:.1f}s"
    )
    return keys, centroids


def batch_similarity_search(
    centroids: np.ndarray,
    embeddings: np.ndarray,
    top_k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute top-K most similar images for each centroid using batch matmul.

    Since both are L2-normalized, dot product = cosine similarity.
    Distance = 1 - similarity (so lower = more similar).

    Returns:
        top_indices: (M, top_k) int array of image indices
        top_distances: (M, top_k) float array of cosine distances
    """
    logger.info(f"Running batch similarity search ({len(centroids)} centroids × {len(embeddings)} images)...")
    t0 = time.time()

    n_centroids = len(centroids)
    actual_top_k = min(top_k, len(embeddings))
    top_indices = np.empty((n_centroids, actual_top_k), dtype=np.int64)
    top_distances = np.empty((n_centroids, actual_top_k), dtype=np.float32)

    # Process in batches to control memory
    for start in range(0, n_centroids, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n_centroids)
        batch = centroids[start:end]

        # Cosine similarity via dot product (both normalized)
        # Shape: (batch_size, n_images)
        similarities = batch @ embeddings.T

        # Convert to distance (lower = more similar)
        distances = 1.0 - similarities

        # Get top-K indices (smallest distances)
        # Use argpartition for O(n) partial sort, then sort the top-K
        if actual_top_k < distances.shape[1]:
            part_idx = np.argpartition(distances, actual_top_k, axis=1)[:, :actual_top_k]
            # Gather the distances for these indices
            batch_dists = np.take_along_axis(distances, part_idx, axis=1)
            # Sort within the top-K
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
                f"  Similarity search: {end}/{n_centroids} "
                f"({progress*100:.0f}%), ETA {eta:.0f}s"
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
    """Filter results to unique species (excluding self) and build final DataFrame."""
    logger.info("Building final results...")
    t0 = time.time()

    # Build img_id -> species lookup from metadata
    img_species_map = dict(zip(
        meta["img_id"].to_list(),
        meta["species"].to_list(),
    ))

    all_rows = []

    for i, (query_species, side) in enumerate(keys):
        seen_species = set()
        rank = 0

        for j in range(top_indices.shape[1]):
            idx = top_indices[i, j]
            img_id = img_ids[idx]
            distance = float(top_distances[i, j])

            # Look up species for this image
            similar_species = img_species_map.get(img_id)
            if similar_species is None:
                continue

            # Normalize for comparison
            normalized_similar = similar_species.lower().replace(" ", "_")

            # Skip self
            if normalized_similar == query_species:
                continue

            # Skip duplicates (one image per species)
            if normalized_similar in seen_species:
                continue

            seen_species.add(normalized_similar)
            rank += 1

            all_rows.append({
                "species": query_species,
                "side": side,
                "similar_species": similar_species,
                "img_id": img_id,
                "distance": distance,
                "rank": rank,
            })

            if rank >= limit:
                break

    result_df = pl.DataFrame(all_rows)
    logger.info(
        f"Built {len(result_df)} result rows in {time.time() - t0:.1f}s"
    )
    return result_df


def create_table(duck_conn, table_name: str, force: bool):
    """Create the species_similarity table in DuckDB."""
    if force:
        duck_conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        logger.info(f"Dropped existing table '{table_name}'")

    duck_conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            species         VARCHAR NOT NULL,
            side            VARCHAR NOT NULL,
            similar_species VARCHAR NOT NULL,
            img_id          VARCHAR NOT NULL,
            distance        DOUBLE NOT NULL,
            rank            INTEGER NOT NULL
        )
    """)
    logger.info(f"Table '{table_name}' ready")


def verify(duck_conn, table_name: str):
    """Print summary statistics."""
    total = duck_conn.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]
    species_count = duck_conn.execute(
        f"SELECT COUNT(DISTINCT species) FROM {table_name}"
    ).fetchone()[0]
    sides = duck_conn.execute(
        f"SELECT side, COUNT(*) FROM {table_name} GROUP BY side"
    ).fetchall()

    logger.info("=" * 50)
    logger.info("VERIFICATION")
    logger.info(f"  Total rows: {total}")
    logger.info(f"  Unique species: {species_count}")
    for side, count in sides:
        logger.info(f"  {side}: {count} rows")
    logger.info("=" * 50)


def main():
    args = parse_args()

    lance_path = os.path.join(args.lance_dir, args.lance_file)
    duck_path = os.path.join(args.duck_dir, args.duck_file)

    # Validate paths
    if not os.path.exists(args.lance_dir):
        logger.error(f"LanceDB directory not found: {args.lance_dir}")
        sys.exit(1)
    if not os.path.exists(duck_path):
        logger.error(f"DuckDB file not found: {duck_path}")
        sys.exit(1)

    start_time = time.time()

    # --- Phase 1: Load data into memory ---
    logger.info(f"Connecting to LanceDB: {lance_path}")
    lance_db = lancedb.connect(lance_path)
    lance_table = lance_db.open_table(args.lance_table)
    logger.info(f"LanceDB table '{args.lance_table}': {lance_table.count_rows()} rows")

    embeddings, img_ids = load_all_embeddings(lance_table)

    logger.info(f"Connecting to DuckDB: {duck_path}")
    duck_conn = duckdb.connect(database=duck_path)
    meta = load_metadata(duck_conn, args.meta_table)

    # --- Phase 2: Compute centroids ---
    species_filter = None
    if args.species:
        species_filter = args.species.strip().lower().replace(" ", "_")
        logger.info(f"Computing for single species: {species_filter}")

    keys, centroids = compute_centroids(meta, embeddings, img_ids, species_filter)

    if len(keys) == 0:
        logger.warning("No species+side groups found. Exiting.")
        duck_conn.close()
        return

    # --- Phase 3: Batch similarity search ---
    top_indices, top_distances = batch_similarity_search(
        centroids, embeddings, args.top_k
    )

    # --- Phase 4: Build filtered results ---
    results_df = build_results(
        keys, top_indices, top_distances, img_ids, meta, args.limit
    )

    # --- Phase 5: Write to DuckDB ---
    create_table(duck_conn, args.similarity_table, args.force)

    if args.species and not args.force:
        duck_conn.execute(
            f"DELETE FROM {args.similarity_table} WHERE species = ?",
            [species_filter],
        )

    if not results_df.is_empty():
        duck_conn.register("_final_results", results_df)
        duck_conn.execute(
            f"INSERT INTO {args.similarity_table} SELECT * FROM _final_results"
        )
        duck_conn.unregister("_final_results")
        logger.info(f"Inserted {len(results_df)} rows into '{args.similarity_table}'")

    # --- Phase 6: Verify ---
    verify(duck_conn, args.similarity_table)
    duck_conn.close()

    elapsed = time.time() - start_time
    logger.info(f"Done! Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
