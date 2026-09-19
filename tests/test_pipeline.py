from __future__ import annotations

from pathlib import Path

import duckdb

from colharmonize.index import ReferenceIndex
from colharmonize.models import ColumnMappings, MatchingConfig
from colharmonize.pipeline import MatchPipeline
from colharmonize.sources import ColSource, OccurrenceSource
from colharmonize.summary import SummaryService


def _run_pipeline(occurrence_db: Path, col_tsv: Path, tmp_path: Path) -> duckdb.DuckDBPyConnection:
    occurrence = OccurrenceSource(occurrence_db, "main.occurrence")
    mappings = ColumnMappings(scientific_name="species")
    with occurrence.connect() as source_connection:
        columns, _ = occurrence.resolve_columns(
            occurrence.columns(source_connection), mappings, strict=True
        )
    index = ReferenceIndex(tmp_path / "cache").ensure(ColSource(col_tsv))
    connection = duckdb.connect(":memory:")
    MatchPipeline(connection, occurrence, columns, index.path, MatchingConfig()).run()
    return connection


def test_matching_methods_and_statuses(occurrence_db: Path, col_tsv: Path, tmp_path: Path) -> None:
    connection = _run_pipeline(occurrence_db, col_tsv, tmp_path)
    try:
        results = dict(
            connection.execute(
                "SELECT original_scientific_name, match_method FROM taxonomy_matches"
            ).fetchall()
        )
        statuses = dict(
            connection.execute(
                "SELECT original_scientific_name, update_status FROM taxonomy_matches"
            ).fetchall()
        )
        assert results["Panthera leo"] == "EXACT_ACCEPTED"
        assert results["Leo leo"] == "EXACT_SYNONYM"
        assert results["Panthera leo Linnaeus"] == "EXACT_CANONICAL"
        assert results["Old alpha"] == "UNIQUE_FAMILY_EPITHET"
        assert results["Panthra tigris"] == "SPELLING_GENUS"
        assert results["Panthera tigrus"] == "SPELLING_EPITHET"
        assert results["Panthra tigrus"] == "FUZZY_TYPO"
        assert statuses["Xenus beta"] == "AMBIGUOUS"
        assert statuses["Nothing nowhere"] == "UNMATCHED"
        assert statuses["Panthera"] == "MATCHED"
        assert results["Panthera"] == "GENUS_EXACT_ACCEPTED"
    finally:
        connection.close()


def test_candidates_are_collapsed_and_limited(
    occurrence_db: Path, col_tsv: Path, tmp_path: Path
) -> None:
    connection = _run_pipeline(occurrence_db, col_tsv, tmp_path)
    try:
        duplicate_count = connection.execute(
            """
            SELECT count(*) FROM (
                SELECT input_taxon_key, accepted_id, count(*)
                FROM taxonomy_candidates
                GROUP BY input_taxon_key, accepted_id
                HAVING count(*) > 1
            )
            """
        ).fetchone()[0]
        assert duplicate_count == 0
        assert (
            connection.execute("SELECT max(candidate_rank) FROM taxonomy_candidates").fetchone()[0]
            <= 5
        )
    finally:
        connection.close()


def test_stable_input_key_and_summary(occurrence_db: Path, col_tsv: Path, tmp_path: Path) -> None:
    first = _run_pipeline(occurrence_db, col_tsv, tmp_path)
    second = _run_pipeline(occurrence_db, col_tsv, tmp_path)
    try:
        first_keys = first.execute(
            "SELECT input_taxon_key FROM input_taxa ORDER BY input_taxon_key"
        ).fetchall()
        second_keys = second.execute(
            "SELECT input_taxon_key FROM input_taxa ORDER BY input_taxon_key"
        ).fetchall()
        assert first_keys == second_keys
        SummaryService().refresh_metrics(first)
        assert first.execute("SELECT count(*) FROM summary_metrics").fetchone()[0] > 0
    finally:
        first.close()
        second.close()
