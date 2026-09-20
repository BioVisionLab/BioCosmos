"""Tests for the locality and coordinate columns on specimen search results.

Both joins are optional by construction. `image_meta_locality` only exists
once LocalityService has run, and `image_meta_coordinates` only once someone
has run `geoharmonize integrate` by hand. Search has to work before either,
so every path is covered with the tables present and absent.

The targeted-search cases matter most: a search on a column whose table is
missing used to reach DuckDB as an unqualified name and fail the whole
request with a binder error, which no test covered.
"""

import pytest

from app.services.metadata import (
    SPECIMEN_COORDINATE_COLUMNS,
    SPECIMEN_LOCALITY_COLUMNS,
    ImageMetaService,
)

OCCURRENCE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, species VARCHAR, family VARCHAR, common_name VARCHAR,
        sex VARCHAR, life_stage VARCHAR, class_dv VARCHAR,
        lat DOUBLE, lon DOUBLE, source_db VARCHAR,
        kingdom VARCHAR, phylum VARCHAR, class VARCHAR, "order" VARCHAR
    )
"""

# Mirrors what LocalityService builds. lat/lon are on the real table too, but
# search never projects them from here -- image_meta already supplies them.
LOCALITY_DDL = """
    CREATE TABLE image_meta_locality (
        img_id VARCHAR, occurrence_id VARCHAR, country_code VARCHAR,
        country VARCHAR, state_province VARCHAR, county VARCHAR,
        municipality VARCHAR, locality VARCHAR, verbatim_locality VARCHAR,
        lat DOUBLE, lon DOUBLE
    )
"""

# Mirrors what `geoharmonize integrate` writes.
COORDINATES_DDL = """
    CREATE TABLE image_meta_coordinates (
        source_id VARCHAR, validation_status VARCHAR, coordinate_check VARCHAR,
        country_check VARCHAR, adm1_check VARCHAR, latitude DOUBLE,
        longitude DOUBLE, recorded_country VARCHAR, recorded_country_code VARCHAR,
        recorded_adm1 VARCHAR, reference_country VARCHAR, reference_adm1 VARCHAR,
        reference_gid_0 VARCHAR, reference_gid_1 VARCHAR, run_id VARCHAR,
        gadm_sha256 VARCHAR
    )
"""


def seed_occurrences(client) -> None:
    client.execute(OCCURRENCE_DDL)
    for img_id, species in [
        ("i1", "danaus_plexippus"),
        ("i2", "coenonympha_pamphilus"),
    ]:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, 'nymphalidae', NULL, NULL, NULL,"
            " 'dorsal', 1.0, 2.0, 'gbif', 'Animalia', 'Arthropoda', 'Insecta',"
            " 'Lepidoptera')",
            [img_id, species],
        )


SEEDED_LOCALITY_COLUMNS = (
    "img_id",
    "country",
    "country_code",
    "state_province",
    "county",
    "municipality",
    "locality",
    "verbatim_locality",
)


def seed_locality(client) -> None:
    client.execute(LOCALITY_DDL)
    columns = ", ".join(SEEDED_LOCALITY_COLUMNS)
    rows = [
        (
            "i1",
            "Brazil",
            "BR",
            "Minas Gerais",
            None,
            "Ouro Preto",
            "Serra do Caraca",
            None,
        ),
        # No GBIF record: the row exists so the join stays one-to-one, but
        # every field is empty.
        ("i2", None, None, None, None, None, None, None),
    ]
    for row in rows:
        assert len(row) == len(SEEDED_LOCALITY_COLUMNS)
        placeholders = ", ".join("?" for _ in row)
        client.execute_prepared(
            f"INSERT INTO image_meta_locality ({columns}) VALUES ({placeholders})",
            list(row),
        )


SEEDED_COORDINATE_COLUMNS = (
    "source_id",
    "validation_status",
    "coordinate_check",
    "country_check",
    "adm1_check",
    "reference_country",
    "reference_adm1",
)


def seed_coordinates(client) -> None:
    client.execute(COORDINATES_DDL)
    columns = ", ".join(SEEDED_COORDINATE_COLUMNS)
    rows = [
        (
            "i1",
            "VALID",
            "VALID_COORDINATE",
            "COUNTRY_MATCH",
            "ADM1_MATCH",
            "Brazil",
            "Minas Gerais",
        ),
        (
            "i2",
            "COUNTRY_MISMATCH",
            "VALID_COORDINATE",
            "COUNTRY_MISMATCH",
            "NOT_EVALUATED",
            "Peru",
            "Cusco",
        ),
    ]
    for row in rows:
        assert len(row) == len(SEEDED_COORDINATE_COLUMNS)
        placeholders = ", ".join("?" for _ in row)
        client.execute_prepared(
            f"INSERT INTO image_meta_coordinates ({columns}) VALUES ({placeholders})",
            list(row),
        )


def build_service(client) -> ImageMetaService:
    service = ImageMetaService.__new__(ImageMetaService)
    service.table = "image_meta"
    service.taxonomy_table = "image_meta_taxonomy"
    service.locality_table = "image_meta_locality"
    service.coordinates_table = "image_meta_coordinates"
    service.db_client = client
    return service


@pytest.fixture
def with_geography(memory_duckdb):
    seed_occurrences(memory_duckdb)
    seed_locality(memory_duckdb)
    seed_coordinates(memory_duckdb)
    return build_service(memory_duckdb)


@pytest.fixture
def without_geography(memory_duckdb):
    seed_occurrences(memory_duckdb)
    return build_service(memory_duckdb)


class TestWithGeography:
    def test_detects_both_tables(self, with_geography):
        assert with_geography._locality_available() is True
        assert with_geography._coordinates_available() is True

    def test_specimens_carry_the_locality(self, with_geography):
        _, specimens, _ = with_geography.search_by_field("species", "%danaus%", 50, 0)
        row = specimens.to_dicts()[0]
        assert row["country"] == "Brazil"
        assert row["state_province"] == "Minas Gerais"
        assert row["municipality"] == "Ouro Preto"

    def test_specimens_carry_the_coordinate_status(self, with_geography):
        _, specimens, _ = with_geography.search_by_field("species", "%danaus%", 50, 0)
        row = specimens.to_dicts()[0]
        assert row["validation_status"] == "VALID"
        assert row["country_check"] == "COUNTRY_MATCH"
        assert row["reference_country"] == "Brazil"

    def test_country_is_searchable(self, with_geography):
        _, specimens, total = with_geography.search_by_field(
            "country", "%brazil%", 50, 0
        )
        assert total == 1
        assert specimens.to_dicts()[0]["img_id"] == "i1"

    def test_validation_status_is_filterable(self, with_geography):
        _, specimens, total = with_geography.search_by_field(
            "validation_status", "%COUNTRY_MISMATCH%", 50, 0
        )
        assert total == 1
        assert specimens.to_dicts()[0]["img_id"] == "i2"

    def test_joins_do_not_inflate_the_count(self, with_geography):
        """Three LEFT JOINs must still yield one row per occurrence."""
        _, specimens, total = with_geography.search_all_fields(
            ["species", "family"], "%nymphalidae%", 50, 0
        )
        assert total == 2
        assert len(specimens) == 2


class TestWithoutGeography:
    def test_detects_the_missing_tables(self, without_geography):
        assert without_geography._locality_available() is False
        assert without_geography._coordinates_available() is False

    def test_payload_keeps_its_shape(self, without_geography):
        """Absent tables project as NULL, so the payload never changes shape."""
        _, specimens, _ = without_geography.search_by_field(
            "species", "%danaus%", 50, 0
        )
        row = specimens.to_dicts()[0]
        for column in SPECIMEN_LOCALITY_COLUMNS + SPECIMEN_COORDINATE_COLUMNS:
            assert column in row, column
            assert row[column] is None, column

    @pytest.mark.parametrize(
        "field",
        ["country", "state_province", "county", "locality", "validation_status"],
    )
    def test_targeted_search_returns_empty_instead_of_raising(
        self, without_geography, field
    ):
        """A search on a column whose table is absent must not fail the request.

        Unqualified, the name is not in the catalog at all and DuckDB rejects
        the statement, taking the whole endpoint down with it.
        """
        _, specimens, total = without_geography.search_by_field(
            field, "%brazil%", 50, 0
        )
        assert total == 0
        assert specimens.is_empty()

    def test_free_text_sweep_still_works(self, without_geography):
        _, _specimens, total = without_geography.search_all_fields(
            ["species", "family", "country"], "%danaus%", 50, 0
        )
        assert total == 1
