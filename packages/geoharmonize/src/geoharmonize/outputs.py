"""Coordinate-validation output artifacts and occurrence write-back."""

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
from harmonize_core.models import TableIdentifier
from harmonize_core.outputs import ArtifactRepository

from geoharmonize.models import WriteBackReport

# What a write-back copies out of `coordinate_validation`, in the order the
# destination table declares them.
#
# `latitude` and `longitude` are the parsed DOUBLEs, null where the recorded
# value could not be read; the original VARCHARs stay behind because the
# occurrence table already holds them. `reference_*` are null unless exactly
# one GADM region matched, so a consumer must read `validation_status` to tell
# "outside every region" from "inside several".
WRITE_BACK_COLUMNS = (
    "source_id",
    "validation_status",
    "coordinate_check",
    "country_check",
    "adm1_check",
    "latitude",
    "longitude",
    "recorded_country",
    "recorded_country_code",
    "recorded_adm1",
    "reference_country",
    "reference_adm1",
    "reference_gid_0",
    "reference_gid_1",
)

# Per-run provenance, carried on every row rather than in a second table so a
# reader needs no join to know which run produced a status.
WRITE_BACK_METADATA_COLUMNS = ("run_id", "gadm_sha256")


class CoordinateOutputRepository(ArtifactRepository):
    """Create coordinate-validation artifacts atomically."""

    database_name = "coordinate_validation.duckdb"
    manifest_name = "coordinate_run.json"
    attach_alias = "geoharmonize_output"

    def write_back(
        self,
        occurrence_db: Path,
        destination_table: str,
        *,
        replace: bool = False,
    ) -> WriteBackReport:
        """Copy the validated coordinates into the occurrence database.

        One row per occurrence, keyed on `source_id`, so a consumer can join it
        straight back to the table the run read. This is the one operation in
        the package that opens the occurrence database for writing; everything
        else treats it as read-only.
        """
        destination = parse_table_identifier(destination_table)
        connection = duckdb.connect(str(occurrence_db))
        try:
            if self._table_exists(connection, destination) and not replace:
                raise OutputError(
                    f"Write-back destination already exists: {destination.display_name}. "
                    "Pass --replace to rebuild it."
                )
            alias = quote_identifier(self.attach_alias)
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                f"ATTACH {quote_literal(str(self.database_path))} AS {alias} (READ_ONLY)"
            )
            connection.execute(
                f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(destination.schema_name)}"
            )
            projection = ",\n                    ".join(
                [f"validation.{quote_identifier(name)}" for name in WRITE_BACK_COLUMNS]
                + [f"metadata.{quote_identifier(name)}" for name in WRITE_BACK_METADATA_COLUMNS]
            )
            connection.execute(
                f"""
                CREATE OR REPLACE TABLE {qualified_name(destination)} AS
                SELECT
                    {projection}
                FROM {alias}.coordinate_validation AS validation
                CROSS JOIN {alias}.coordinate_run_metadata AS metadata
                WHERE validation.source_id IS NOT NULL
                ORDER BY validation.source_row_number
                """
            )
            written = connection.execute(
                f"SELECT count(*), count(DISTINCT source_id) FROM {qualified_name(destination)}"
            ).fetchone()
            assert written is not None
            skipped = connection.execute(
                f"SELECT count(*) FROM {alias}.coordinate_validation WHERE source_id IS NULL"
            ).fetchone()
            assert skipped is not None
            index_name = quote_identifier(f"{destination.table_name}_source_id_idx")
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {qualified_name(destination)} (source_id)"
            )
            connection.execute("COMMIT")
        except Exception:
            with suppress(duckdb.Error):
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return WriteBackReport(
            table=destination.display_name,
            row_count=written[0],
            distinct_source_ids=written[1],
            skipped_null_source_ids=skipped[0],
        )

    @staticmethod
    def _table_exists(connection: duckdb.DuckDBPyConnection, destination: TableIdentifier) -> bool:
        row = connection.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [destination.schema_name, destination.table_name],
        ).fetchone()
        assert row is not None
        return bool(row[0])
