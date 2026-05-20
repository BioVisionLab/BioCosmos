#!/usr/bin/env python3
"""
Precompute per-species visual similarity and store results in DuckDB.

Mirrors the exact runtime logic from SpeciesSimilarity.find_similar_species():
  1. For each species, get image IDs from image_meta
  2. Filter by dorsal/ventral side
  3. Fetch UNICOM embeddings from LanceDB
  4. Compute centroid
  5. Query LanceDB for top-K similar (cosine distance)
  6. Merge with metadata, filter unique species, remove self
  7. Store payload-ready rows in DuckDB

Usage:
    cd backend
    .venv/bin/python scripts/precompute_similarity.py \
        --lance-dir lance_db_lite --duck-dir duck_db

    # Single species test:
    .venv/bin/python scripts/precompute_similarity.py \
        --lance-dir lance_db_lite --duck-dir duck_db --species "vanessa_cardui"

    # Force recreate:
    .venv/bin/python scripts/precompute_similarity.py \
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

# Defaults matching the runtime configuration
DEFAULT_LANCE_FILE = "biocosmos.lance"
DEFAULT_DUCK_FILE = "biocosmos.duckdb"
DEFAULT_LANCE_TABLE = "nymphalidae"
DEFAULT_META_TABLE = "image_meta"
DEFAULT_SIMILARITY_TABLE = "species_similarity"
DEFAULT_TOP_K = 20  # LanceDB vector search limit (pre-dedup)
DEFAULT_LIMIT = 10  # Final similar species per side (matches runtime)
SIDES = ["dorsal", "ventral"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precompute per-species visual similarity."
    )
    parser.add_argument(
        "--lance-dir",
        default="lance_db_lite",
        help="LanceDB directory (default: lance_db_lite)",
    )
    parser.add_argument(
        "--duck-dir",
        default="duck_db",
        help="DuckDB directory (default: duck_db)",
    )
    parser.add_argument(
        "--lance-file",
        default=DEFAULT_LANCE_FILE,
        help=f"LanceDB filename (default: {DEFAULT_LANCE_FILE})",
    )
    parser.add_argument(
        "--duck-file",
        default=DEFAULT_DUCK_FILE,
        help=f"DuckDB filename (default: {DEFAULT_DUCK_FILE})",
    )
    parser.add_argument(
        "--lance-table",
        default=DEFAULT_LANCE_TABLE,
        help=f"LanceDB table name (default: {DEFAULT_LANCE_TABLE})",
    )
    parser.add_argument(
        "--meta-table",
        default=DEFAULT_META_TABLE,
        help=f"DuckDB metadata table (default: {DEFAULT_META_TABLE})",
    )
    parser.add_argument(
        "--similarity-table",
        default=DEFAULT_SIMILARITY_TABLE,
        help=f"DuckDB output table (default: {DEFAULT_SIMILARITY_TABLE})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Vector search limit before dedup (default: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Final similar species per side (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and recreate the similarity table",
    )
    parser.add_argument(
        "--species",
        type=str,
        default=None,
        help="Compute for a single species (for testing)",
    )
    return parser.parse_args()


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


def get_all_species(duck_conn, meta_table: str) -> list[str]:
    """Get all unique normalized species names from image_meta."""
    result = duck_conn.execute(f"""
        SELECT DISTINCT REPLACE(LOWER(species), ' ', '_') AS species
        FROM {meta_table}
        ORDER BY species
    """).fetchall()
    return [row[0] for row in result]


def get_image_ids_for_side(
    duck_conn, meta_table: str, species: str, side: str
) -> list[str]:
    """Get image IDs for a species + side. Mirrors _filter_by_side."""
    result = duck_conn.execute(
        f"""
        SELECT img_id FROM {meta_table}
        WHERE REPLACE(LOWER(species), ' ', '_') = ?
          AND LOWER(class_dv) = ?
        """,
        [species, side.lower()],
    ).fetchall()
    return [row[0] for row in result]


def fetch_embeddings_batch(
    lance_table, image_ids: list[str]
) -> np.ndarray:
    """Fetch UNICOM embeddings for image IDs. Returns Nx768 array."""
    if not image_ids:
        return np.array([])

    ids_sql = ", ".join(f"'{img_id}'" for img_id in image_ids)
    where_clause = f"img_id IN ({ids_sql})"

    results = (
        lance_table.search()
        .where(where_clause)
        .limit(len(image_ids))
        .select(["img_id", "unicom_embeddings"])
        .to_polars()
    )

    if results.is_empty():
        return np.array([])

    return np.array(results["unicom_embeddings"].to_list())


def query_similar(
    lance_table, centroid: np.ndarray, top_k: int
) -> pl.DataFrame | None:
    """Query LanceDB for similar images. Mirrors _query_embedding."""
    results = (
        lance_table.search(
            centroid,
            vector_column_name="unicom_embeddings",
        )
        .distance_type("cosine")
        .limit(top_k)
        .to_polars()
    )

    safe_cols = [c for c in ("img_id", "_distance") if c in results.columns]
    if not safe_cols:
        return None

    cleaned = results.select(safe_cols).rename(
        {"img_id": "imgId", "_distance": "distance"}
    )
    cleaned = cleaned.unique(subset=["imgId"])
    return cleaned


def merge_with_metadata(
    duck_conn, meta_table: str, results: pl.DataFrame
) -> pl.DataFrame | None:
    """Merge search results with image_meta. Mirrors _merge_result_with_metadata."""
    duck_conn.register("_tmp_results", results)
    try:
        merged = duck_conn.execute(f"""
            SELECT
                t.*,
                m.species,
                m.source_db,
                m.class_dv
            FROM _tmp_results t
            INNER JOIN {meta_table} m ON t.imgId = m.img_id
        """).pl()
    finally:
        duck_conn.unregister("_tmp_results")

    if merged is None or merged.is_empty():
        return None
    return merged


def filter_by_species(results: pl.DataFrame, species: str) -> pl.DataFrame:
    """Keep one best image per species, remove self. Mirrors _filter_by_species + _filter_similar_images."""
    # Keep best (lowest distance) per species
    filtered = results.sort("distance", descending=False).unique(
        subset=["species"], maintain_order=True
    )
    # Remove self-species (same normalization as runtime)
    filtered = filtered.filter(
        pl.col("species").str.to_lowercase().str.replace_all(" ", "_", literal=True)
        != species.lower().replace(" ", "_")
    )
    return filtered


def compute_for_species_side(
    species: str,
    side: str,
    lance_table,
    duck_conn,
    meta_table: str,
    top_k: int,
    limit: int,
) -> list[dict]:
    """Compute similarity for one species + one side. Returns payload-ready rows."""
    # Step 1: Get image IDs for this species + side
    image_ids = get_image_ids_for_side(duck_conn, meta_table, species, side)
    if not image_ids:
        return []

    # Step 2: Fetch UNICOM embeddings
    embeddings = fetch_embeddings_batch(lance_table, image_ids)
    if embeddings.size == 0:
        return []

    # Step 3: Compute centroid
    centroid = np.mean(embeddings, axis=0)

    # Step 4: Query LanceDB
    results = query_similar(lance_table, centroid, top_k)
    if results is None or results.is_empty():
        return []

    # Step 5: Merge with metadata
    merged = merge_with_metadata(duck_conn, meta_table, results)
    if merged is None or merged.is_empty():
        return []

    # Step 6: Filter (unique species, remove self)
    filtered = filter_by_species(merged, species)
    if filtered.is_empty():
        return []

    # Step 7: Take top `limit` and build output rows
    filtered = filtered.head(limit)
    rows = []
    for rank, row in enumerate(filtered.iter_rows(named=True), 1):
        rows.append({
            "species": species,
            "side": side,
            "similar_species": row["species"],
            "img_id": row["imgId"],
            "distance": row["distance"],
            "rank": rank,
        })
    return rows


def flush_results(duck_conn, results: list[dict], table_name: str):
    """Insert accumulated results into DuckDB."""
    if not results:
        return
    df = pl.DataFrame(results)
    duck_conn.register("_batch_results", df)
    try:
        duck_conn.execute(
            f"INSERT INTO {table_name} SELECT * FROM _batch_results"
        )
    finally:
        duck_conn.unregister("_batch_results")


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

    # Connect
    logger.info(f"Connecting to LanceDB: {lance_path}")
    lance_db = lancedb.connect(lance_path)
    lance_table = lance_db.open_table(args.lance_table)
    logger.info(f"LanceDB table '{args.lance_table}': {lance_table.count_rows()} rows")

    logger.info(f"Connecting to DuckDB: {duck_path}")
    duck_conn = duckdb.connect(database=duck_path)

    # Create output table
    create_table(duck_conn, args.similarity_table, args.force)

    # Get species list
    if args.species:
        species_list = [args.species.strip().lower().replace(" ", "_")]
        # Delete existing rows for this species (for single-species recompute)
        duck_conn.execute(
            f"DELETE FROM {args.similarity_table} WHERE species = ?",
            [species_list[0]],
        )
        logger.info(f"Computing for single species: {species_list[0]}")
    else:
        species_list = get_all_species(duck_conn, args.meta_table)
    logger.info(f"Processing {len(species_list)} species")

    # Main loop
    all_results = []
    total = len(species_list)
    start_time = time.time()
    skipped = 0

    for i, species in enumerate(species_list):
        for side in SIDES:
            rows = compute_for_species_side(
                species=species,
                side=side,
                lance_table=lance_table,
                duck_conn=duck_conn,
                meta_table=args.meta_table,
                top_k=args.top_k,
                limit=args.limit,
            )
            if rows:
                all_results.extend(rows)
            else:
                skipped += 1

        # Progress
        if (i + 1) % 50 == 0 or i == total - 1:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            logger.info(
                f"[{i + 1}/{total}] {elapsed:.1f}s elapsed, "
                f"~{eta:.1f}s remaining, {len(all_results)} rows buffered"
            )

        # Flush every 1000 rows to bound memory
        if len(all_results) >= 1000:
            flush_results(duck_conn, all_results, args.similarity_table)
            all_results.clear()

    # Final flush
    if all_results:
        flush_results(duck_conn, all_results, args.similarity_table)

    logger.info(f"Skipped {skipped} species+side combos (no images or no results)")

    # Verify
    verify(duck_conn, args.similarity_table)
    duck_conn.close()
    logger.info("Done!")


if __name__ == "__main__":
    main()
