from pathlib import Path

import duckdb
import pytest
from harmonize_core.errors import SourceValidationError

from geoharmonize.models import CoordinateColumnMappings
from geoharmonize.sources import CoordinateOccurrenceSource


def test_coordinate_columns_are_detected(coordinate_db: Path) -> None:
    source = CoordinateOccurrenceSource(coordinate_db, "main.occurrence")
    with source.connect() as connection:
        resolved, warnings = source.resolve_coordinate_columns(
            source.columns(connection), CoordinateColumnMappings(), strict=True
        )
    assert not warnings
    assert resolved == {
        "source_id": "occurrenceID",
        "latitude": "decimalLatitude",
        "longitude": "decimalLongitude",
        "country": "country",
        "adm1": "stateProvince",
    }


def test_inspect_counts_distinct_points(coordinate_db: Path) -> None:
    source = CoordinateOccurrenceSource(coordinate_db, "main.occurrence")
    report = source.inspect(CoordinateColumnMappings())
    assert report.valid
    assert report.row_count == 13
    assert report.detected_columns["latitude"] == "decimalLatitude"


def test_img_id_is_detected_as_a_source_id(tmp_path: Path) -> None:
    """BioCosmos keys occurrences on img_id rather than a Darwin Core id."""
    path = tmp_path / "images.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE images(img_id VARCHAR, lat DOUBLE, lon DOUBLE)")
    finally:
        connection.close()

    source = CoordinateOccurrenceSource(path, "main.images")
    with source.connect() as connection:
        available = source.columns(connection)
    resolved, warnings = source.resolve_coordinate_columns(
        available, CoordinateColumnMappings(), strict=True
    )
    assert resolved["source_id"] == "img_id"
    assert resolved["latitude"] == "lat"
    assert resolved["longitude"] == "lon"
    assert warnings == []


def test_invalid_mapping_identifies_field_table_and_inspection_command(tmp_path: Path) -> None:
    path = tmp_path / "images.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE images(img_id VARCHAR, lat DOUBLE, lon DOUBLE)")
    finally:
        connection.close()

    source = CoordinateOccurrenceSource(path, "main.images")
    with source.connect() as connection:
        available = source.columns(connection)

    with pytest.raises(SourceValidationError) as raised:
        source.resolve_coordinate_columns(
            available,
            CoordinateColumnMappings(country="country_code"),
            strict=True,
        )

    message = str(raised.value)
    assert "country=country_code" in message
    assert "main.images" in message
    assert "geoharmonize inspect" in message
    assert "--list-columns main.images" in message
