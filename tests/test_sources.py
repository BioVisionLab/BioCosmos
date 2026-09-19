from pathlib import Path

from colharmonize.models import ColumnMappings, CoordinateColumnMappings
from colharmonize.sources import DuckDBCatalog, OccurrenceSource


def test_catalog_lists_tables_and_columns(occurrence_db: Path) -> None:
    catalog = DuckDBCatalog(occurrence_db)
    tables = catalog.list_tables()
    assert [(item.schema_name, item.table_name) for item in tables] == [("main", "occurrence")]
    columns = catalog.list_columns("main.occurrence")
    assert columns[0].name == "occurrenceID"
    assert columns[0].data_type == "VARCHAR"


def test_inspect_requires_choice_when_both_name_columns_exist(occurrence_db: Path) -> None:
    source = OccurrenceSource(occurrence_db, "main.occurrence")
    report = source.inspect(ColumnMappings())
    assert not report.valid
    assert any("Both scientificName and species" in warning for warning in report.warnings)


def test_inspect_with_explicit_species_mapping(occurrence_db: Path) -> None:
    source = OccurrenceSource(occurrence_db, "main.occurrence")
    report = source.inspect(ColumnMappings(scientific_name="species"))
    assert report.valid
    assert report.row_count == 11
    assert report.detected_columns["scientific_name"] == "species"


def test_coordinate_columns_are_detected(coordinate_db: Path) -> None:
    source = OccurrenceSource(coordinate_db, "main.occurrence")
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
