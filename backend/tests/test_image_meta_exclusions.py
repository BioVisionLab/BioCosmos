"""Tests for the image_meta view that leaves excluded families out.

Castniidae are moths imaged with the butterflies. Their rows stay in the raw
source table, but every reader queries the view, so no query or analysis
counts them.
"""

import pytest

from app.services.metadata import ImageMetaService

ROWS = [
    ("img1", "Nymphalidae", "danaus_plexippus"),
    ("img2", "Castniidae", "castnia_invaria"),
    ("img3", " castniidae ", "telchin_licus"),
    ("img4", None, "unknown_species"),
    ("img5", "Pieridae", "colias_eurytheme"),
]


def seed(client, table: str) -> None:
    client.execute(
        f"CREATE TABLE {table} (img_id VARCHAR, family VARCHAR, species VARCHAR)"
    )
    for row in ROWS:
        client.execute_prepared(f"INSERT INTO {table} VALUES (?, ?, ?)", list(row))


def service(client, exclude=("castniidae",), skip=True) -> ImageMetaService:
    svc = ImageMetaService(client)
    svc.table = "image_meta"
    svc.source_table = "image_meta_source"
    svc.exclude_families = list(exclude)
    svc.skip_ingestion = skip
    return svc


def ids(client, table: str) -> list[str]:
    rows = client.execute(f"SELECT img_id FROM {table} ORDER BY img_id").fetchall()
    return [row[0] for row in rows]


def test_legacy_table_moves_to_source_and_view_excludes(memory_duckdb):
    seed(memory_duckdb, "image_meta")
    service(memory_duckdb).apply_exclusions()

    assert memory_duckdb.table_type("image_meta") == "VIEW"
    assert memory_duckdb.table_type("image_meta_source") == "BASE TABLE"
    # Case and whitespace variants are caught; an unknown family is kept.
    assert ids(memory_duckdb, "image_meta") == ["img1", "img4", "img5"]
    # The raw rows are kept.
    assert len(ids(memory_duckdb, "image_meta_source")) == len(ROWS)


def test_apply_exclusions_is_idempotent(memory_duckdb):
    seed(memory_duckdb, "image_meta")
    svc = service(memory_duckdb)
    svc.apply_exclusions()
    svc.apply_exclusions()
    assert ids(memory_duckdb, "image_meta") == ["img1", "img4", "img5"]


def test_view_columns_are_visible_to_column_checks(memory_duckdb):
    seed(memory_duckdb, "image_meta_source")
    service(memory_duckdb).apply_exclusions()
    assert memory_duckdb.column_exists("image_meta", "family")
    assert memory_duckdb.table_exists("image_meta")


def test_no_exclusions_passes_every_row(memory_duckdb):
    seed(memory_duckdb, "image_meta_source")
    service(memory_duckdb, exclude=()).apply_exclusions()
    assert len(ids(memory_duckdb, "image_meta")) == len(ROWS)


def test_quotes_in_family_names_are_escaped(memory_duckdb):
    seed(memory_duckdb, "image_meta_source")
    service(memory_duckdb, exclude=("o'dd", "castniidae")).apply_exclusions()
    assert ids(memory_duckdb, "image_meta") == ["img1", "img4", "img5"]


def test_missing_source_leaves_nothing(memory_duckdb):
    service(memory_duckdb).apply_exclusions()
    assert memory_duckdb.table_type("image_meta") is None


def test_both_tables_present_is_refused(memory_duckdb):
    seed(memory_duckdb, "image_meta")
    seed(memory_duckdb, "image_meta_source")
    with pytest.raises(RuntimeError):
        service(memory_duckdb).apply_exclusions()


def test_ingest_writes_the_source_table(memory_duckdb, tmp_path):
    parquet = tmp_path / "meta.parquet"
    seed(memory_duckdb, "staging")
    memory_duckdb.execute(f"COPY staging TO '{parquet}' (FORMAT parquet)")
    # A legacy raw table is moved aside before the new rows land.
    seed(memory_duckdb, "image_meta")

    svc = service(memory_duckdb, skip=False)
    svc.format = "parquet"
    svc.path = str(parquet)
    svc.ingest()
    svc.apply_exclusions()

    assert memory_duckdb.table_type("image_meta_source") == "BASE TABLE"
    assert ids(memory_duckdb, "image_meta") == ["img1", "img4", "img5"]
