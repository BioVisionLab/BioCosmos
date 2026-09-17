"""Atomic output database and optional occurrence lookup writing."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import duckdb

from colharmonize.errors import OutputError
from colharmonize.identifiers import (
    parse_table_identifier,
    qualified_name,
    quote_identifier,
    quote_literal,
)
from colharmonize.models import RunManifest


class OutputRepository:
    """Own output creation and the narrowly scoped write-back transaction."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.database_path = output_dir / "taxonomy_update.duckdb"

    @contextmanager
    def build_database(self, *, force: bool) -> Iterator[duckdb.DuckDBPyConnection]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.database_path.exists() and not force:
            raise OutputError(f"Output database already exists: {self.database_path}")
        temporary = self.output_dir / f".taxonomy_update.{uuid.uuid4().hex}.duckdb"
        connection = duckdb.connect(str(temporary))
        try:
            yield connection
            connection.execute("CHECKPOINT")
            connection.close()
            os.replace(temporary, self.database_path)
        except Exception:
            connection.close()
            temporary.unlink(missing_ok=True)
            raise

    def write_manifest(self, manifest: RunManifest, *, force: bool) -> Path:
        destination = self.output_dir / "run.json"
        if destination.exists() and not force:
            raise OutputError(f"Manifest already exists: {destination}")
        temporary = self.output_dir / f".run.{uuid.uuid4().hex}.json"
        temporary.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
        return destination

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
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                f"ATTACH {quote_literal(str(self.database_path))} "
                "AS colharmonize_output (READ_ONLY)"
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
                    matches.accepted_authorship,
                    matches.accepted_family,
                    matches.match_method,
                    matches.match_score,
                    matches.update_status,
                    matches.candidate_count,
                    metadata.run_id,
                    metadata.col_sha256
                FROM colharmonize_output.input_taxon_variants variants
                JOIN colharmonize_output.taxonomy_matches matches USING (input_taxon_key)
                CROSS JOIN colharmonize_output.run_metadata metadata
                """
            )
            connection.execute("COMMIT")
        except Exception:
            with suppress(duckdb.Error):
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
