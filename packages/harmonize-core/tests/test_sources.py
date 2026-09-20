from pathlib import Path

from harmonize_core.sources import DuckDBCatalog


def test_catalog_lists_tables_and_columns(occurrence_db: Path) -> None:
    catalog = DuckDBCatalog(occurrence_db)
    tables = catalog.list_tables()
    assert [(item.schema_name, item.table_name) for item in tables] == [("main", "occurrence")]
    columns = catalog.list_columns("main.occurrence")
    assert columns[0].name == "occurrenceID"
    assert columns[0].data_type == "VARCHAR"
