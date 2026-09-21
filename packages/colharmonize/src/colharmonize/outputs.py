"""Taxonomy output database and optional occurrence lookup writing."""

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


class OutputRepository(ArtifactRepository):
    """Own output creation and the narrowly scoped write-back transaction."""

    database_name = "taxonomy_update.duckdb"
    manifest_name = "run.json"
    attach_alias = "colharmonize_output"

    def write_back(self, occurrence_db: Path, destination_table: str) -> None:
        destination = parse_table_identifier(destination_table)
        connection = duckdb.connect(str(occurrence_db))
        try:
            exists_row = connection.execute(
                """
                SELECT count(*)
                FROM information_schema.tables
                WHERE table_schema = ? AND table_name = ?
                """,
                [destination.schema_name, destination.table_name],
            ).fetchone()
            assert exists_row is not None
            exists = exists_row[0]
            if exists:
                raise OutputError(
                    f"Write-back destination already exists: {destination.display_name}"
                )
            alias = quote_identifier(self.attach_alias)
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                f"ATTACH {quote_literal(str(self.database_path))} AS {alias} (READ_ONLY)"
            )
            connection.execute(
                f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(destination.schema_name)}"
            )
            connection.execute(
                f"""
                CREATE TABLE {qualified_name(destination)} AS
                SELECT
                    variants.original_scientific_name,
                    variants.original_genus,
                    variants.original_specific_epithet,
                    variants.original_infraspecific_epithet,
                    variants.original_family,
                    variants.original_order,
                    variants.original_class,
                    variants.original_kingdom,
                    variants.original_taxon_rank,
                    variants.original_authorship,
                    variants.input_taxon_key,
                    variants.occurrence_count,
                    matches.accepted_id,
                    matches.accepted_name,
                    matches.accepted_species_name,
                    matches.accepted_rank,
                    matches.alternative_matches,
                    matches.accepted_authorship,
                    matches.accepted_family,
                    matches.match_method,
                    matches.match_score,
                    matches.update_status,
                    matches.candidate_count,
                    metadata.run_id,
                    metadata.col_sha256
                FROM {alias}.input_taxon_variants variants
                JOIN {alias}.taxonomy_matches matches USING (input_taxon_key)
                CROSS JOIN {alias}.run_metadata metadata
                """
            )
            connection.execute("COMMIT")
        except Exception:
            with suppress(duckdb.Error):
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
