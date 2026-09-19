from pathlib import Path

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
    assert report.row_count == 12
    assert report.detected_columns["latitude"] == "decimalLatitude"
