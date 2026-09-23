"""Tests for the institution directory.

Exercised against a real in-memory DuckDB, like test_provenance_service.py,
with the resolver stubbed so no test touches the GBIF registry.
"""

import threading

import duckdb
import pytest
from instharmonize import Institution, MatchSource

from app.database.duckdb import DuckDBClient
from app.database.ingestion_state import IngestionState
from app.services.institution import (
    UPDATE_SOURCE_KEY,
    InstitutionDirectory,
    InstitutionService,
)

TABLE = "institution_directory"


class MemoryDuckDBClient(DuckDBClient):
    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self.lock = threading.RLock()


class StubResolver:
    """Names every code it is asked about, and records which it was asked."""

    def __init__(self, fingerprint="v1:a", failing=()):
        self.fingerprint = fingerprint
        self.failing = set(failing)
        self.asked: list[set[str]] = []
        self.records = []

    def resolve_all(self, records):
        records = list(records)
        self.records.extend(records)
        codes = {record.institution_code.strip() for record in records}
        self.asked.append(codes)
        return {
            code: Institution(code=code, retry=True)
            if code in self.failing
            else Institution(
                code=code,
                name=f"{code} Museum",
                homepage=f"https://{code.lower()}.example/",
                source=MatchSource.GRSCICOLL_EXACT,
            )
            for code in codes
        }


def build_service(client, resolver) -> InstitutionService:
    service = InstitutionService.__new__(InstitutionService)
    service.skip = False
    service.table = TABLE
    service.overrides_path = None
    service.image_meta_table = "image_meta"
    service.gbif_table = "gbif_meta"
    service.db_client = client
    service._resolver = resolver
    return service


def build_directory(client) -> InstitutionDirectory:
    directory = InstitutionDirectory.__new__(InstitutionDirectory)
    directory.table = TABLE
    directory.db_client = client
    return directory


@pytest.fixture
def client():
    client = MemoryDuckDBClient()
    client.execute("CREATE TABLE image_meta (img_id VARCHAR, uuid VARCHAR)")
    client.execute(
        """
        CREATE TABLE gbif_meta (
            "gbifID" BIGINT, "occurrenceID" VARCHAR, "institutionCode" VARCHAR,
            "datasetKey" VARCHAR, "publisher" VARCHAR
        )
        """
    )
    client.execute(
        """
        INSERT INTO image_meta VALUES
            ('i1', 'occ-mcz'), ('i2', 'occ-mcz-2'), ('i3', 'occ-dup'),
            ('i4', 'occ-blank'), ('i5', 'no-gbif-record')
        """
    )
    client.execute(
        """
        INSERT INTO gbif_meta VALUES
            (1, 'occ-mcz', 'MCZ', 'd1', 'Harvard'),
            (2, 'occ-mcz-2', ' MCZ ', 'd1', 'Harvard'),
            (3, 'occ-dup', NULL, 'd2', 'Somewhere'),
            (4, 'occ-dup', 'NHMUK', 'd2', 'Natural History Museum'),
            (5, 'occ-blank', '', 'd3', 'Nobody'),
            -- Not behind any image, so never resolved.
            (6, 'occ-unused', 'YPM', 'd4', 'Yale')
        """
    )
    yield client
    client.conn.close()


def test_resolves_only_codes_behind_images(client):
    resolver = StubResolver()
    added = build_service(client, resolver).ensure()

    assert added == 2
    assert resolver.asked == [{"MCZ", "NHMUK"}]
    mcz = [r for r in resolver.records if r.institution_code.strip() == "MCZ"]
    assert [(r.dataset_key, r.occurrences) for r in mcz] == [("d1", 2)]


def test_directory_reads_back_resolved_codes(client):
    build_service(client, StubResolver()).ensure()
    directory = build_directory(client).get_all()
    assert directory["MCZ"] == {
        "name": "MCZ Museum",
        "homepage": "https://mcz.example/",
        "country": None,
        "source": "grscicoll_exact",
    }


def test_second_run_asks_the_registry_nothing(client):
    build_service(client, StubResolver()).ensure()
    resolver = StubResolver()
    assert build_service(client, resolver).ensure() == 0
    assert resolver.asked == []


def test_registry_failures_are_retried_next_time(client):
    build_service(client, StubResolver(failing={"NHMUK"})).ensure()
    assert set(build_directory(client).get_all()) == {"MCZ"}

    resolver = StubResolver()
    build_service(client, resolver).ensure()
    assert resolver.asked == [{"NHMUK"}]


def test_changed_fingerprint_resolves_everything_again(client):
    build_service(client, StubResolver(fingerprint="v1:a")).ensure()
    resolver = StubResolver(fingerprint="v2:a")
    build_service(client, resolver).ensure()

    assert resolver.asked == [{"MCZ", "NHMUK"}]
    assert IngestionState(client).get(UPDATE_SOURCE_KEY) == "v2:a"


def test_unresolved_codes_are_stored_but_not_listed(client):
    class Unnamed(StubResolver):
        def resolve_all(self, records):
            codes = {r.institution_code.strip() for r in records}
            return {code: Institution(code=code) for code in codes}

    build_service(client, Unnamed()).ensure()

    stored = client.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    assert stored == 2
    assert build_directory(client).get_all() == {}


def test_missing_gbif_table_is_a_no_op(client):
    client.execute("DROP TABLE gbif_meta")
    resolver = StubResolver()
    assert build_service(client, resolver).ensure() == 0
    assert resolver.asked == []


def test_missing_directory_reads_empty(client):
    assert build_directory(client).get_all() == {}
    assert build_directory(client).get("MCZ") is None


def test_single_code_lookup(client):
    build_service(client, StubResolver()).ensure()
    directory = build_directory(client)

    assert directory.get(" MCZ ")["homepage"] == "https://mcz.example/"
    assert directory.get("YPM") is None
    assert directory.get(None) is None
