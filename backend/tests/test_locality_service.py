"""Tests for the per-occurrence locality table.

The service is mostly one large SQL statement, so it is exercised against a
real DuckDB rather than a fake: the dedupe, the placeholder filtering and the
country-name join are the behaviour under test, and none of them survive being
mocked out.
"""

import threading

import duckdb
import pytest

from app.database.duckdb import DuckDBClient
from app.services.locality import (
    LocalityService,
    OccurrenceCoordinates,
    OccurrenceLocality,
    country_name_frame,
    locality_display,
)

OCCURRENCE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, uuid VARCHAR, species VARCHAR, lat DOUBLE, lon DOUBLE
    )
"""

# The columns the fixture rows supply, named so that a column added to the
# table above does not have to be threaded through every row below.
GBIF_DDL = """
    CREATE TABLE gbif_meta (
        "gbifID" BIGINT, "occurrenceID" VARCHAR, "countryCode" VARCHAR,
        "stateProvince" VARCHAR, "county" VARCHAR, "municipality" VARCHAR,
        "locality" VARCHAR, "verbatimLocality" VARCHAR
    )
"""


class MemoryDuckDBClient(DuckDBClient):
    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self.lock = threading.RLock()


def build_service(client) -> LocalityService:
    service = LocalityService.__new__(LocalityService)
    service.skip = False
    service.table = "image_meta_locality"
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
            ('i1', 'occ-brazil', 'a', -20.0, -43.0),
            ('i2', 'occ-bolivia', 'b', -17.0, -65.0),
            ('i3', 'occ-placeholder', 'c', 1.0, 2.0),
            ('i4', 'occ-duplicated', 'd', 3.0, 4.0),
            ('i5', 'occ-kosovo', 'e', 42.0, 21.0),
            ('i6', 'occ-unknown-code', 'f', 5.0, 6.0),
            ('i7', 'no-gbif-record', 'g', 7.0, 8.0)
        """
    )
    client.execute(
        """
        INSERT INTO gbif_meta VALUES
            (1, 'occ-brazil', 'BR', 'Minas Gerais', NULL, 'Ouro Preto', 'Serra do Caraca', NULL),
            (2, 'occ-bolivia', 'BO', 'La Paz', NULL, NULL, 'Coroico', NULL),
            (3, 'occ-placeholder', 'US', NULL, NULL, NULL,
                '[no specific locality data]', '[no verbatim locality data]'),
            -- The same occurrenceID twice: the sparser row has the lower id, so
            -- picking by id alone would lose the locality.
            (4, 'occ-duplicated', NULL, NULL, NULL, NULL, NULL, NULL),
            (5, 'occ-duplicated', 'PE', 'Cusco', NULL, NULL, 'Machu Picchu', NULL),
            (6, 'occ-kosovo', 'XK', NULL, NULL, NULL, NULL, NULL),
            (7, 'occ-unknown-code', 'ZZ', NULL, NULL, NULL, NULL, NULL)
        """
    )
    yield client
    client.conn.close()


@pytest.fixture
def built(client):
    build_service(client)._build()
    return client


def rows_by_img(client) -> dict:
    result = client.execute("SELECT * FROM image_meta_locality").pl()
    return {row["img_id"]: row for row in result.to_dicts()}


def test_one_row_per_occurrence(built):
    """The join must not fan out, even where gbif_meta duplicates a key."""
    total = built.execute("SELECT count(*) FROM image_meta_locality").fetchone()[0]
    assert total == 7


def test_duplicate_occurrence_ids_keep_the_most_complete_row(built):
    row = rows_by_img(built)["i4"]
    assert row["country"] == "Peru"
    assert row["locality"] == "Machu Picchu"


def test_gbif_placeholders_become_null(built):
    """'[no specific locality data]' is a note about absence, not a place."""
    row = rows_by_img(built)["i3"]
    assert row["locality"] is None
    assert row["verbatim_locality"] is None
    assert row["country"] == "United States"


def test_common_name_is_preferred_over_the_treaty_form(built):
    """pycountry's `name` for BO is "Bolivia, Plurinational State of"."""
    assert rows_by_img(built)["i2"]["country"] == "Bolivia"


def test_codes_pycountry_lacks(built):
    rows = rows_by_img(built)
    # XK is supplemented by hand; ZZ means "unknown" and stays unresolved.
    assert rows["i5"]["country"] == "Kosovo"
    assert rows["i6"]["country"] is None
    assert rows["i6"]["country_code"] == "ZZ"


def test_occurrences_without_a_gbif_record_still_get_a_row(built):
    row = rows_by_img(built)["i7"]
    assert row["occurrence_id"] is None
    assert row["country"] is None
    # lat/lon come from image_meta, so they survive an unmatched join.
    assert row["lat"] == 7.0


def test_coordinates_are_carried_for_geoharmonize(built):
    """The table has to be a sufficient input for `geoharmonize integrate`."""
    columns = {
        row[0] for row in built.execute("DESCRIBE image_meta_locality").fetchall()
    }
    assert {"lat", "lon", "country_code", "state_province"} <= columns


def test_country_name_frame_covers_the_iso_list():
    frame = country_name_frame()
    names = dict(zip(frame["country_code"].to_list(), frame["country_name"].to_list()))
    assert names["US"] == "United States"
    assert names["BO"] == "Bolivia"
    assert names["TW"] == "Taiwan"
    assert names["XK"] == "Kosovo"
    assert "ZZ" not in names


class TestEnsure:
    def test_skips_when_gbif_is_absent(self, caplog):
        client = MemoryDuckDBClient()
        client.execute(OCCURRENCE_DDL)
        service = build_service(client)
        assert service.ensure() is False
        assert not client.table_exists("image_meta_locality")

    def test_is_idempotent(self, client):
        service = build_service(client)
        assert service.ensure() is True
        assert service.ensure() is False

    def test_rebuilds_when_the_schema_version_moves(self, client, monkeypatch):
        service = build_service(client)
        assert service.ensure() is True
        monkeypatch.setattr("app.services.locality.LOCALITY_SCHEMA_VERSION", 2)
        assert service.ensure() is True


class TestLocalityDisplay:
    def test_orders_from_coarsest_to_finest(self):
        assert (
            locality_display(
                {
                    "country": "Brazil",
                    "stateProvince": "Minas Gerais",
                    "municipality": "Ouro Preto",
                    "locality": "Serra do Caraca",
                }
            )
            == "Brazil, Minas Gerais, Ouro Preto, Serra do Caraca"
        )

    def test_skips_empty_ranks(self):
        assert (
            locality_display({"country": "Peru", "locality": "Cusco"}) == "Peru, Cusco"
        )

    def test_falls_back_to_the_verbatim_form(self):
        """165,046 occurrences carry only the verbatim locality."""
        assert (
            locality_display({"country": "Peru", "verbatimLocality": "nr. Cusco"})
            == "Peru, nr. Cusco"
        )

    def test_drops_a_rank_that_repeats_one_already_written(self):
        """Publishers routinely set municipality and locality to one string."""
        assert (
            locality_display(
                {
                    "country": "Brazil",
                    "municipality": "Ouro Preto",
                    "locality": "ouro preto",
                }
            )
            == "Brazil, Ouro Preto"
        )

    def test_drops_a_repeat_that_differs_only_in_accents(self):
        """Real GBIF records write one place two ways in adjacent ranks."""
        assert (
            locality_display(
                {
                    "country": "Brazil",
                    "stateProvince": "Sao Paulo",
                    "locality": "São Paulo",
                }
            )
            == "Brazil, Sao Paulo"
        )

    def test_keeps_genuinely_different_accented_names(self):
        assert (
            locality_display(
                {
                    "country": "Brazil",
                    "stateProvince": "Minas Gerais",
                    "locality": "Serra do Caraça",
                }
            )
            == "Brazil, Minas Gerais, Serra do Caraça"
        )

    def test_none_when_nothing_survives(self):
        assert locality_display({"country": None, "locality": "  "}) is None


class TestReaders:
    def test_locality_block_carries_a_display_line(self, built):
        block = OccurrenceLocality(built).get_for_image("i1")
        assert block["display"] == "Brazil, Minas Gerais, Ouro Preto, Serra do Caraca"
        assert block["countryCode"] == "BR"

    def test_locality_block_is_none_when_nothing_was_recorded(self, built):
        assert OccurrenceLocality(built).get_for_image("i7") is None

    def test_coordinates_block_is_none_without_the_table(self, built):
        """`geoharmonize integrate` has not run, so the table is simply absent."""
        assert OccurrenceCoordinates(built).get_for_image("i1") is None
