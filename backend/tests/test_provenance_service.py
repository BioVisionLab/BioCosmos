"""Tests for the per-occurrence provenance table.

Mirrors test_locality_service.py: mostly one large SQL statement, so it is
exercised against a real DuckDB rather than a fake.
"""

import threading

import duckdb
import pytest

from app.database.duckdb import DuckDBClient
from app.services.provenance import OccurrenceProvenance, ProvenanceService

OCCURRENCE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, uuid VARCHAR, species VARCHAR
    )
"""

GBIF_DDL = """
    CREATE TABLE gbif_meta (
        "gbifID" BIGINT, "occurrenceID" VARCHAR, "institutionCode" VARCHAR,
        "catalogNumber" VARCHAR
    )
"""


class MemoryDuckDBClient(DuckDBClient):
    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self.lock = threading.RLock()


def build_service(client) -> ProvenanceService:
    service = ProvenanceService.__new__(ProvenanceService)
    service.skip = False
    service.table = "image_meta_provenance"
    service.image_meta_table = "image_meta"
    service.gbif_table = "gbif_meta"
    service.db_client = client
    return service


@pytest.fixture
def client():
    client = MemoryDuckDBClient()
    client.execute(OCCURRENCE_DDL)
    client.execute(GBIF_DDL)
    client.execute(
        """
        INSERT INTO image_meta VALUES
            ('i1', 'occ-mcz', 'a'),
            ('i2', 'occ-duplicated', 'b'),
            ('i3', 'occ-blank', 'c'),
            ('i4', 'no-gbif-record', 'd')
        """
    )
    client.execute(
        """
        INSERT INTO gbif_meta VALUES
            (1, 'occ-mcz', 'MCZ', '100018'),
            -- The same occurrenceID twice: the sparser row has the lower id,
            -- so picking by id alone would lose the institution.
            (2, 'occ-duplicated', NULL, NULL),
            (3, 'occ-duplicated', 'NHMUK', '4471029'),
            (4, 'occ-blank', '', '  ')
        """
    )
    yield client
    client.conn.close()


@pytest.fixture
def built(client):
    build_service(client)._build()
    return client


def rows_by_img(client) -> dict:
    result = client.execute("SELECT * FROM image_meta_provenance").pl()
    return {row["img_id"]: row for row in result.to_dicts()}


def test_one_row_per_occurrence(built):
    """The join must not fan out, even where gbif_meta duplicates a key."""
    total = built.execute("SELECT count(*) FROM image_meta_provenance").fetchone()[0]
    assert total == 4


def test_reads_institution_and_catalog_number(built):
    row = rows_by_img(built)["i1"]
    assert row["institution_code"] == "MCZ"
    assert row["catalog_number"] == "100018"


def test_duplicate_occurrence_ids_keep_the_most_complete_row(built):
    row = rows_by_img(built)["i2"]
    assert row["institution_code"] == "NHMUK"
    assert row["catalog_number"] == "4471029"


def test_blank_strings_become_null(built):
    row = rows_by_img(built)["i3"]
    assert row["institution_code"] is None
    assert row["catalog_number"] is None


def test_occurrences_without_a_gbif_record_still_get_a_row(built):
    row = rows_by_img(built)["i4"]
    assert row["occurrence_id"] is None
    assert row["institution_code"] is None


class TestEnsure:
    def test_skips_when_gbif_is_absent(self):
        client = MemoryDuckDBClient()
        client.execute(OCCURRENCE_DDL)
        service = build_service(client)
        assert service.ensure() is False
        assert not client.table_exists("image_meta_provenance")

    def test_is_idempotent(self, client):
        service = build_service(client)
        assert service.ensure() is True
        assert service.ensure() is False

    def test_rebuilds_when_the_schema_version_moves(self, client, monkeypatch):
        service = build_service(client)
        assert service.ensure() is True
        monkeypatch.setattr("app.services.provenance.PROVENANCE_SCHEMA_VERSION", 2)
        assert service.ensure() is True

    def test_skip_flag(self, client):
        service = build_service(client)
        service.skip = True
        assert service.ensure() is False
        assert not client.table_exists("image_meta_provenance")


class TestOccurrenceProvenance:
    @pytest.fixture
    def reader(self, built):
        service = OccurrenceProvenance.__new__(OccurrenceProvenance)
        from app.services.locality import _OccurrenceBlockReader

        service._reader = _OccurrenceBlockReader(
            built,
            "image_meta_provenance",
            (
                ("institution_code", "institutionCode"),
                ("catalog_number", "catalogNumber"),
            ),
        )
        return service

    def test_returns_camel_cased_keys(self, reader):
        block = reader.get_for_image("i1")
        assert block == {"institutionCode": "MCZ", "catalogNumber": "100018"}

    def test_none_when_nothing_was_recorded(self, reader):
        assert reader.get_for_image("i3") is None

    def test_none_without_a_gbif_record(self, reader):
        assert reader.get_for_image("i4") is None

    def test_none_without_the_table(self, client):
        service = OccurrenceProvenance.__new__(OccurrenceProvenance)
        from app.services.locality import _OccurrenceBlockReader

        service._reader = _OccurrenceBlockReader(
            client,
            "image_meta_provenance",
            (
                ("institution_code", "institutionCode"),
                ("catalog_number", "catalogNumber"),
            ),
        )
        assert service.get_for_image("i1") is None
