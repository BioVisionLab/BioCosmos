"""Species diversity by validated country: the population and the routes.

The population must match panel G of `analyses/notebooks/data_summary.ipynb`,
so these mirror the notebook's own country-mapping tests.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.query.country_diversity import CountryDiversity
from app.routers.data_stats import get_country_diversity, router

TAXONOMY_DDL = """
    CREATE TABLE image_meta_taxonomy (
        img_id VARCHAR, update_status VARCHAR, accepted_species_name VARCHAR,
        accepted_rank VARCHAR, accepted_name VARCHAR
    )
"""

COORDINATES_DDL = """
    CREATE TABLE image_meta_coordinates (
        source_id VARCHAR, country_check VARCHAR, reference_gid_0 VARCHAR,
        reference_country VARCHAR
    )
"""

# img_id, update_status, accepted species, rank, accepted name,
# country_check, GID_0, GADM country
ROWS = [
    (
        "i1",
        "MATCHED",
        "Danaus plexippus",
        "species",
        "Danaus plexippus",
        "COUNTRY_MATCH",
        "USA",
        "United States",
    ),
    (
        "i2",
        "MATCHED",
        "Danaus plexippus",
        "species",
        "Danaus plexippus",
        "COUNTRY_MATCH",
        "USA",
        "United States",
    ),
    # No country recorded: imputed from the coordinate.
    (
        "i3",
        "MATCHED",
        "Vanessa cardui",
        "species",
        "Vanessa cardui",
        "COUNTRY_NOT_PROVIDED",
        "USA",
        "United States",
    ),
    # A subspecies groups with its species.
    (
        "i4",
        "MATCHED",
        "Danaus plexippus",
        "subspecies",
        "Danaus plexippus plexippus",
        "COUNTRY_MATCH",
        "USA",
        "United States",
    ),
    # Two GADM codes normalize to one country; the species is counted once.
    (
        "i5",
        "MATCHED",
        "Papilio machaon",
        "species",
        "Papilio machaon",
        "COUNTRY_MATCH",
        "IND",
        "India",
    ),
    (
        "i6",
        "MATCHED",
        "Papilio machaon",
        "species",
        "Papilio machaon",
        "COUNTRY_MATCH",
        "Z01",
        "India",
    ),
    # Ineligible: country contradicted, taxonomy unresolved, genus-only.
    (
        "i7",
        "MATCHED",
        "Vanessa atalanta",
        "species",
        "Vanessa atalanta",
        "COUNTRY_MISMATCH",
        "CAN",
        "Canada",
    ),
    ("i8", "AMBIGUOUS", None, None, None, "COUNTRY_MATCH", "CAN", "Canada"),
    ("i9", "MATCHED", None, "genus", "Vanessa", "COUNTRY_MATCH", "CAN", "Canada"),
    # Eligible, but the GADM reference resolves to no country.
    (
        "i10",
        "MATCHED",
        "Vanessa cardui",
        "species",
        "Vanessa cardui",
        "COUNTRY_MATCH",
        "Z09",
        "Disputed",
    ),
]


@pytest.fixture
def seeded(memory_duckdb):
    memory_duckdb.execute("CREATE TABLE image_meta (img_id VARCHAR)")
    memory_duckdb.execute(TAXONOMY_DDL)
    memory_duckdb.execute(COORDINATES_DDL)
    for row in ROWS:
        memory_duckdb.execute_prepared("INSERT INTO image_meta VALUES (?)", [row[0]])
        memory_duckdb.execute_prepared(
            "INSERT INTO image_meta_taxonomy VALUES (?, ?, ?, ?, ?)", list(row[:5])
        )
        memory_duckdb.execute_prepared(
            "INSERT INTO image_meta_coordinates VALUES (?, ?, ?, ?)", [row[0], *row[5:]]
        )
    return memory_duckdb


def test_summary_counts_only_eligible_records(seeded):
    summary = CountryDiversity(seeded).summary()
    assert summary["countries"] == [
        {
            "countryCode": "US",
            "countryName": "United States",
            "speciesCount": 2,
            "imageCount": 4,
            "imputedImageCount": 1,
        },
        {
            "countryCode": "IN",
            "countryName": "India",
            "speciesCount": 1,
            "imageCount": 2,
            "imputedImageCount": 0,
        },
    ]
    assert summary["mappedImages"] == 6
    assert summary["imputedImages"] == 1
    assert summary["unresolvedImages"] == 1


def test_species_list_is_case_insensitive(seeded):
    payload = CountryDiversity(seeded).species("us")
    assert payload["countryCode"] == "US"
    assert payload["species"] == [
        {"species": "Danaus plexippus", "imageCount": 3, "imputedImageCount": 0},
        {"species": "Vanessa cardui", "imageCount": 1, "imputedImageCount": 1},
    ]


def test_species_list_for_unknown_or_empty_country(seeded):
    service = CountryDiversity(seeded)
    assert service.species("ZZ") is None
    assert service.species("CA") is None


def test_missing_coordinate_table_degrades_to_none(memory_duckdb):
    service = CountryDiversity(memory_duckdb)
    assert service.summary() is None
    assert service.species("US") is None


def _client(service) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_country_diversity] = lambda: service
    return TestClient(app)


def test_routes_serve_cached_payloads(seeded):
    client = _client(CountryDiversity(seeded))
    response = client.get("/stats/country")
    assert response.status_code == 200
    assert "max-age" in response.headers["cache-control"]
    assert response.json()["countries"][0]["countryCode"] == "US"
    species = client.get("/stats/country/in")
    assert species.status_code == 200
    assert species.json()["countryName"] == "India"


@pytest.mark.parametrize("code", ["ZZ", "CA", "USA", "1A"])
def test_country_route_404s(seeded, code):
    response = _client(CountryDiversity(seeded)).get(f"/stats/country/{code}")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_summary_route_404s_without_coordinates(memory_duckdb):
    response = _client(CountryDiversity(memory_duckdb)).get("/stats/country")
    assert response.status_code == 404


def test_dependency_reuses_one_instance(memory_duckdb):
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(duck_db=memory_duckdb))
    )
    assert get_country_diversity(request) is get_country_diversity(request)
