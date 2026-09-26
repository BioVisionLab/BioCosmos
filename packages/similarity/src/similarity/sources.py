"""Read the image embeddings (LanceDB) and image metadata (DuckDB)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import polars as pl
from harmonize_core.errors import SourceValidationError
from harmonize_core.identifiers import parse_table_identifier, qualified_name

logger = logging.getLogger(__name__)

EMBEDDING_COLUMN = "unicom_embeddings"
# Rows per Arrow batch streamed out of LanceDB.
READ_BATCH_SIZE = 50_000


def open_embeddings(lance_dir: Path, table: str):
    """Open the LanceDB table holding the image embeddings."""
    import lancedb

    if not lance_dir.exists():
        raise SourceValidationError(f"LanceDB directory not found: {lance_dir}")
    try:
        return lancedb.connect(str(lance_dir)).open_table(table)
    except Exception as exc:  # lancedb raises bare ValueError/FileNotFoundError
        raise SourceValidationError(f"Cannot open LanceDB table {table!r}: {exc}") from exc


def load_all_embeddings(
    lance_table, column: str = EMBEDDING_COLUMN
) -> tuple[np.ndarray, np.ndarray]:
    """Load every embedding and img_id into memory, L2-normalized.

    Goes through the search builder rather than the table's lazy
    `to_polars()`, which is broken by the pinned polars/lancedb pair.

    Returns:
        embeddings: (N, D) float32 array, L2-normalized
        img_ids: (N,) array of image ID strings
    """
    logger.info("Loading all embeddings into memory...")
    t0 = time.time()

    ids: list[np.ndarray] = []
    blocks: list[np.ndarray] = []
    query = lance_table.search().select(["img_id", column]).limit(None)
    for batch in query.to_batches(READ_BATCH_SIZE):
        if batch.num_rows == 0:
            continue
        values = batch.column(column)
        width = values.type.list_size
        ids.append(np.asarray(batch.column("img_id").to_pylist(), dtype=object))
        blocks.append(
            values.flatten().to_numpy(zero_copy_only=False).astype(np.float32).reshape(-1, width)
        )
    if not blocks:
        return np.empty((0, 0), dtype=np.float32), np.empty(0, dtype=object)
    img_ids = np.concatenate(ids)
    embeddings = np.concatenate(blocks)

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
    """Load image metadata (img_id, species, side) into a Polars DataFrame.

    `meta_table` defaults to the backend's `image_meta` view, which already
    leaves out the families in `image_metadata.exclude_families`.
    """
    logger.info("Loading image metadata...")
    table = qualified_name(parse_table_identifier(meta_table))
    meta = duck_conn.execute(f"""
        SELECT img_id,
               REPLACE(LOWER(species), ' ', '_') AS species,
               LOWER(class_dv) AS side
        FROM {table}
    """).pl()
    logger.info(f"Loaded {len(meta)} metadata rows")
    return meta
