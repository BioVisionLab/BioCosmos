"""Freshness tracking for ingested data sources.

Existing ingestion uses ``CREATE TABLE IF NOT EXISTS``, so a changed source
file with an unchanged name is silently ignored. This table records what each
source looked like when it was last loaded, letting a service skip the reload
when nothing changed and redo it when something did.
"""

import logging
import os

from .duckdb import DuckDBClient

logger = logging.getLogger(__name__)

TABLE_NAME = "ingestion_state"


def file_fingerprint(path: str) -> str | None:
    """Return a cheap change token for a file, or None when it is missing.

    Size and modification time rather than a content digest: the CoL name
    usage table is roughly 3 GB, and hashing it on every boot would cost
    seconds just to decide to do nothing.
    """
    try:
        stat = os.stat(path)
    except OSError as error:
        logger.info(f"Cannot fingerprint '{path}': {error}")
        return None
    return f"{stat.st_size}:{int(stat.st_mtime)}"


class IngestionState:
    """Read and write the per-source freshness markers."""

    def __init__(self, duckdb: DuckDBClient):
        self.db_client = duckdb
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.db_client.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                source_key VARCHAR PRIMARY KEY,
                fingerprint VARCHAR,
                run_id VARCHAR,
                loaded_at TIMESTAMP
            )
            """
        )

    def get(self, source_key: str) -> str | None:
        """Return the fingerprint recorded for a source, or None."""
        result = self.db_client.execute_prepared_to_pl(
            f"SELECT fingerprint FROM {TABLE_NAME} WHERE source_key = ?",
            [source_key],
        )
        if result is None or result.is_empty():
            return None
        return result["fingerprint"][0]

    def is_current(self, source_key: str, fingerprint: str | None) -> bool:
        """True when the source is already loaded at this fingerprint."""
        if fingerprint is None:
            return False
        return self.get(source_key) == fingerprint

    def mark(
        self,
        source_key: str,
        fingerprint: str | None,
        *,
        run_id: str | None = None,
    ) -> None:
        """Record that a source has been loaded at this fingerprint."""
        self.db_client.execute_prepared(
            f"""
            INSERT INTO {TABLE_NAME} (source_key, fingerprint, run_id, loaded_at)
            VALUES (?, ?, ?, current_timestamp)
            ON CONFLICT (source_key) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                run_id = excluded.run_id,
                loaded_at = excluded.loaded_at
            """,
            [source_key, fingerprint, run_id],
        )
        logger.info(f"Recorded ingestion state for '{source_key}'.")
