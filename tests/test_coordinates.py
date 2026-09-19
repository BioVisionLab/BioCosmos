from __future__ import annotations

from pathlib import Path

import duckdb

from colharmonize.coordinates import (
    CoordinateValidationPipeline,
    normalize_adm1,
    normalize_geographic_name,
    resolve_country_code,
)
from colharmonize.geography import GadmSource
from colharmonize.models import CoordinateColumnMappings, CoordinateValidationConfig
from colharmonize.sources import OccurrenceSource


def _run_coordinate_pipeline(
    coordinate_db: Path, gadm_gpkg: Path
) -> duckdb.DuckDBPyConnection:
    occurrence = OccurrenceSource(coordinate_db, "main.occurrence")
    with occurrence.connect() as source_connection:
        columns, _ = occurrence.resolve_coordinate_columns(
            occurrence.columns(source_connection), CoordinateColumnMappings(), strict=True
        )
    gadm = GadmSource(gadm_gpkg)
    info = gadm.inspect()
    connection = duckdb.connect(":memory:")
    pipeline = CoordinateValidationPipeline(
        connection,
        occurrence,
        columns,
        gadm,
        info,
        CoordinateValidationConfig(),
    )
    pipeline.run()
    pipeline.refresh_metrics()
    return connection


def test_name_normalization_and_country_resolution() -> None:
    assert resolve_country_code("US") == "USA"
    assert resolve_country_code("United States") == "USA"
    assert resolve_country_code("not a country") is None
    assert normalize_adm1("Québec Province") == "quebec"
    assert normalize_geographic_name("Côte d'Ivoire") == "cotedivoire"


def test_coordinate_checks_and_locality_statuses(
    coordinate_db: Path, gadm_gpkg: Path
) -> None:
    connection = _run_coordinate_pipeline(coordinate_db, gadm_gpkg)
    try:
        statuses = dict(
            connection.execute(
                "SELECT source_id, validation_status FROM coordinate_validation"
            ).fetchall()
        )
        assert statuses["valid-name"] == "VALID"
        assert statuses["valid-code"] == "VALID"
        assert statuses["valid-no-locality"] == "VALID"
        assert statuses["country-mismatch"] == "COUNTRY_MISMATCH"
        assert statuses["adm1-mismatch"] == "ADM1_MISMATCH"
        assert statuses["missing"] == "MISSING_COORDINATE"
        assert statuses["unparseable"] == "MISSING_COORDINATE"
        assert statuses["latitude-range"] == "COORDINATE_OUT_OF_RANGE"
        assert statuses["longitude-range"] == "COORDINATE_OUT_OF_RANGE"
        assert statuses["zero"] == "ZERO_COORDINATE"
        assert statuses["no-reference"] == "NO_REFERENCE_MATCH"
        assert statuses["ambiguous"] == "AMBIGUOUS_REFERENCE"

        component = connection.execute(
            """
            SELECT country_check, adm1_check, reference_gid_0, reference_adm1
            FROM coordinate_validation WHERE source_id = 'valid-name'
            """
        ).fetchone()
        assert component == ("COUNTRY_MATCH", "ADM1_MATCH", "USA", "Florida")
    finally:
        connection.close()


def test_spatial_work_uses_distinct_points_and_retains_candidates(
    coordinate_db: Path, gadm_gpkg: Path
) -> None:
    connection = _run_coordinate_pipeline(coordinate_db, gadm_gpkg)
    try:
        assert connection.execute("SELECT count(*) FROM coordinate_points").fetchone()[0] == 3
        duplicate_point = connection.execute(
            """
            SELECT occurrence_count FROM coordinate_points
            WHERE latitude = 5 AND longitude = 5
            """
        ).fetchone()
        assert duplicate_point == (5,)
        ambiguous_count = connection.execute(
            """
            SELECT reference_match_count FROM coordinate_validation
            WHERE source_id = 'ambiguous'
            """
        ).fetchone()
        assert ambiguous_count == (2,)
        assert (
            connection.execute("SELECT count(*) FROM coordinate_reference_subset").fetchone()[0]
            == 2
        )
    finally:
        connection.close()


def test_coordinate_summary_metrics(coordinate_db: Path, gadm_gpkg: Path) -> None:
    connection = _run_coordinate_pipeline(coordinate_db, gadm_gpkg)
    try:
        pipeline_count = connection.execute(
            "SELECT count(*) FROM coordinate_validation"
        ).fetchone()[0]
        assert pipeline_count == 12
        assert (
            connection.execute(
                """
                SELECT sum(record_count) FROM coordinate_summary_metrics
                WHERE metric_group = 'validation_status'
                """
            ).fetchone()[0]
            == 12
        )
    finally:
        connection.close()
