"""Write the `species_similarity` table the backend reads."""

from __future__ import annotations

import logging

import polars as pl
from harmonize_core.identifiers import parse_table_identifier, qualified_name

logger = logging.getLogger(__name__)


def write_results(
    duck_conn,
    table_name: str,
    results: pl.DataFrame,
    *,
    species: str | None = None,
    force: bool = False,
) -> None:
    """Replace the similarity rows in one transaction.

    A full run replaces every row; a single-species run replaces only that
    species' rows. `force` drops and recreates the table first.
    """
    table = qualified_name(parse_table_identifier(table_name))
    duck_conn.execute("BEGIN TRANSACTION")
    try:
        if force:
            duck_conn.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info(f"Dropped existing table '{table_name}'")
        duck_conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                species         VARCHAR NOT NULL,
                side            VARCHAR NOT NULL,
                similar_species VARCHAR NOT NULL,
                img_id          VARCHAR NOT NULL,
                distance        DOUBLE NOT NULL,
                rank            INTEGER NOT NULL
            )
        """)
        if species is None:
            duck_conn.execute(f"DELETE FROM {table}")
        else:
            duck_conn.execute(f"DELETE FROM {table} WHERE species = ?", [species])
        if not results.is_empty():
            duck_conn.register("_final_results", results)
            try:
                duck_conn.execute(f"INSERT INTO {table} SELECT * FROM _final_results")
            finally:
                duck_conn.unregister("_final_results")
        duck_conn.execute("COMMIT")
    except Exception:
        duck_conn.execute("ROLLBACK")
        raise
    logger.info(f"Wrote {len(results)} rows into '{table_name}'")


def summarize(duck_conn, table_name: str) -> dict[str, int]:
    """Row, species and per-side counts of the written table."""
    table = qualified_name(parse_table_identifier(table_name))
    total, species = duck_conn.execute(
        f"SELECT count(*), count(DISTINCT species) FROM {table}"
    ).fetchone()
    counts = {"rows": int(total), "species": int(species)}
    for side, count in duck_conn.execute(
        f"SELECT side, count(*) FROM {table} GROUP BY side ORDER BY side"
    ).fetchall():
        counts[f"{side}_rows"] = int(count)
    return counts
