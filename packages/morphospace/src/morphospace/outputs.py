"""Morphospace run artifacts and the write-back into the backend database."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

import duckdb
from harmonize_core.errors import OutputError
from harmonize_core.identifiers import (
    parse_table_identifier,
    qualified_name,
    quote_identifier,
    quote_literal,
)
from harmonize_core.outputs import ArtifactRepository

from morphospace.models import WriteBackReport

# Artifact table -> the columns a reader looks rows up by. The backend's
# default destination for each is `morphospace_<table>`, as listed under
# `morphospace:` in backend/app/configs/config.yaml.
TABLE_INDEXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "scope": (("scope_rank", "scope_key"),),
    "points": (("scope_rank", "scope_key"), ("accepted_species",)),
    "species": (("accepted_species",), ("page_key",)),
    "disparity": (("scope_rank", "scope_key"),),
    "extremes": (("scope_rank", "scope_key"),),
}

DEFAULT_PREFIX = "morphospace"


def default_destinations(prefix: str = DEFAULT_PREFIX) -> dict[str, str]:
    return {name: f"{prefix}_{name}" for name in TABLE_INDEXES}


class MorphospaceOutputRepository(ArtifactRepository):
    """Create one run's DuckDB output and manifest atomically."""

    database_name = "morphospace.duckdb"
    manifest_name = "morphospace_run.json"
    attach_alias = "morphospace_output"

    def write_back(
        self,
        backend_db: Path,
        destinations: dict[str, str] | None = None,
        *,
        replace: bool = False,
    ) -> WriteBackReport:
        """Copy every artifact table into the backend database in one transaction.

        Either all five tables are replaced or none is, so the backend never
        serves points from one run with disparity from another.
        """
        if not self.database_path.is_file():
            raise OutputError(f"Run artifact not found: {self.database_path}")
        targets = {
            name: parse_table_identifier(table)
            for name, table in (destinations or default_destinations()).items()
        }
        connection = duckdb.connect(str(backend_db))
        written: dict[str, int] = {}
        try:
            existing = [t.display_name for t in targets.values() if _exists(connection, t)]
            if existing and not replace:
                raise OutputError(
                    f"Write-back destination already exists: {', '.join(existing)}. "
                    "Pass --replace to rebuild it."
                )
            alias = quote_identifier(self.attach_alias)
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                f"ATTACH {quote_literal(str(self.database_path))} AS {alias} (READ_ONLY)"
            )
            for name, target in targets.items():
                destination = qualified_name(target)
                connection.execute(
                    f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(target.schema_name)}"
                )
                connection.execute(
                    f"CREATE OR REPLACE TABLE {destination} AS "
                    f"SELECT * FROM {alias}.{quote_identifier(name)}"
                )
                for number, columns in enumerate(TABLE_INDEXES[name]):
                    index = quote_identifier(f"{target.table_name}_idx{number}")
                    column_list = ", ".join(quote_identifier(c) for c in columns)
                    connection.execute(
                        f"CREATE INDEX IF NOT EXISTS {index} ON {destination} ({column_list})"
                    )
                row = connection.execute(f"SELECT count(*) FROM {destination}").fetchone()
                assert row is not None
                written[target.display_name] = int(row[0])
            connection.execute("COMMIT")
        except Exception:
            with suppress(duckdb.Error):
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return WriteBackReport(tables=written)


def _exists(connection: duckdb.DuckDBPyConnection, table) -> bool:
    row = connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [table.schema_name, table.table_name],
    ).fetchone()
    assert row is not None
    return bool(row[0])
