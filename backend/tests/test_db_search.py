import pytest
import duckdb
import polars as pl
import threading
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.database.duckdb import DuckDBClient
from app.query.db_search import TextToDbSearch
from app.routers.db_search import router

# A custom DuckDBClient for testing that uses an in-memory connection
class MockDuckDBClient(DuckDBClient):
    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self.conn.execute("INSTALL fts;")
        self.conn.execute("LOAD fts;")
        self.lock = threading.RLock()


@pytest.fixture(scope="module")
def populated_duckdb():
    client = MockDuckDBClient()
    # Create image_meta table with representative mock columns
    # We populate with various specimens to test matching, normalization, coordinates, and pagination
    client.conn.execute("""
        CREATE TABLE image_meta (
            img_id VARCHAR,
            species VARCHAR,
            family VARCHAR,
            common_name VARCHAR,
            sex VARCHAR,
            life_stage VARCHAR,
            class_dv VARCHAR,
            lat DOUBLE,
            lon DOUBLE,
            source_db VARCHAR,
            kingdom VARCHAR,
            phylum VARCHAR,
            class VARCHAR,
            "order" VARCHAR,
            tax_rank VARCHAR,
            tax_status VARCHAR
        )
    """)
    
    # Insert test data:
    # - Danaus plexippus (binomial + subspecies + author version)
    # - Coenonympha pamphilus (for pagination)
    # - Coordinates (near LA: 34.0522, -118.2437)
    client.conn.execute("""
        INSERT INTO image_meta VALUES
        ('img1', 'Danaus plexippus', 'Nymphalidae', 'Monarch', 'female', 'adult', 'dorsal', 34.0522, -118.2437, 'GBIF', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted'),
        ('img2', 'Danaus plexippus plexippus', 'Nymphalidae', 'Monarch', 'male', 'adult', 'ventral', 34.0525, -118.2439, 'GBIF', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'subspecies', 'accepted'),
        ('img3', 'Danaus plexippus Linnaeus', 'Nymphalidae', 'Monarch', NULL, 'larva', 'dorsal', 34.0521, -118.2435, 'iNaturalist', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted'),
        ('img4', 'Coenonympha pamphilus', 'Nymphalidae', 'Small Heath', 'male', 'adult', 'dorsal', 51.5074, -0.1278, 'GBIF', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted'),
        ('img5', 'Coenonympha pamphilus', 'Nymphalidae', 'Small Heath', 'male', 'adult', 'ventral', 51.5075, -0.1279, 'GBIF', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted'),
        ('img6', 'Coenonympha pamphilus', 'Nymphalidae', 'Small Heath', 'male', 'pupa', 'dorsal', 51.5076, -0.1280, 'GBIF', 'Animalia', 'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted')
    """)
    # Provenance for two of the occurrences: img1 held by a resolved
    # institution, img4 by a code instharmonize could not name. The rest have
    # no row, as for an occurrence with no GBIF record.
    client.conn.execute("""
        CREATE TABLE image_meta_provenance (
            img_id VARCHAR, occurrence_id VARCHAR,
            institution_code VARCHAR, catalog_number VARCHAR
        )
    """)
    client.conn.execute("""
        INSERT INTO image_meta_provenance VALUES
        ('img1', 'occ1', 'NHMUK', 'BMNH(E) 1234567'),
        ('img4', 'occ4', 'XYZ', 'XYZ-42')
    """)
    client.conn.execute("""
        CREATE TABLE institution_directory (
            code VARCHAR PRIMARY KEY, name VARCHAR, homepage VARCHAR,
            country VARCHAR, grscicoll_key VARCHAR, source VARCHAR,
            resolved_at TIMESTAMP
        )
    """)
    client.conn.execute("""
        INSERT INTO institution_directory VALUES
        ('NHMUK', 'Natural History Museum, London', 'https://www.nhm.ac.uk',
         'GB', NULL, 'grscicoll', NULL)
    """)
    yield client
    client.close()


@pytest.fixture
def mock_request(populated_duckdb):
    req = MagicMock(spec=Request)
    app = MagicMock()
    app.state = MagicMock()
    app.state.duck_db = populated_duckdb
    req.app = app
    return req


def test_db_search_binomial_normalization(mock_request):
    # Search for 'danaus plexippus' (space) - should match 'Danaus plexippus' and 'Danaus plexippus plexippus'
    # and extract the base binomial name 'danaus_plexippus'
    searcher = TextToDbSearch(request=mock_request, query="danaus plexippus", field="all")
    res = searcher.search()
    assert res is not None
    assert len(res["results"]) == 1
    assert res["results"][0]["species"] == "danaus_plexippus"
    # Should get all 3 specimens
    assert len(res["specimens"]) == 3
    assert res["total_specimens"] == 3


def test_db_search_carries_specimen_provenance(mock_request):
    """Catalog number and holder travel per row, named when resolved."""
    res = TextToDbSearch(
        request=mock_request, query="danaus plexippus", field="all"
    ).search()
    assert res is not None
    by_id = {s["img_id"]: s for s in res["specimens"]}
    assert by_id["img1"]["catalog_number"] == "BMNH(E) 1234567"
    assert by_id["img1"]["institution_code"] == "NHMUK"
    assert by_id["img1"]["institution_name"] == "Natural History Museum, London"
    assert by_id["img1"]["institution_homepage"] == "https://www.nhm.ac.uk"
    # No provenance row: every field present, and None.
    for key in (
        "catalog_number",
        "institution_code",
        "institution_name",
        "institution_homepage",
    ):
        assert by_id["img2"][key] is None, key


def test_db_search_unresolved_institution_keeps_its_code(mock_request):
    res = TextToDbSearch(
        request=mock_request, query="coenonympha pamphilus", field="all"
    ).search()
    assert res is not None
    by_id = {s["img_id"]: s for s in res["specimens"]}
    assert by_id["img4"]["catalog_number"] == "XYZ-42"
    assert by_id["img4"]["institution_code"] == "XYZ"
    assert by_id["img4"]["institution_name"] is None
    assert by_id["img4"]["institution_homepage"] is None


def test_db_search_field_filtering(mock_request):
    # Search for 'male' in 'sex' field
    searcher = TextToDbSearch(request=mock_request, query="male", field="sex")
    res = searcher.search()
    assert res is not None
    # 2 danaus plexippus (1 male, 1 female because "female" contains "male"), 3 coenonympha pamphilus (3 male) = 5 total
    assert len(res["specimens"]) == 5
    for spec in res["specimens"]:
        assert spec["sex"] in ("male", "female")


def test_db_search_pagination(mock_request):
    # Test page 1 with limit 2
    searcher = TextToDbSearch(request=mock_request, query="coenonympha pamphilus", field="all", page=1, limit=2)
    res1 = searcher.search()
    assert res1 is not None
    assert len(res1["specimens"]) == 2
    assert res1["total_specimens"] == 3
    assert res1["page"] == 1
    assert res1["limit"] == 2
    
    # Test page 2 with limit 2
    searcher_page2 = TextToDbSearch(request=mock_request, query="coenonympha pamphilus", field="all", page=2, limit=2)
    res2 = searcher_page2.search()
    assert res2 is not None
    assert len(res2["specimens"]) == 1
    assert res2["total_specimens"] == 3
    assert res2["page"] == 2
    
    # Confirm offsets return different records
    ids1 = {s["img_id"] for s in res1["specimens"]}
    ids2 = {s["img_id"] for s in res2["specimens"]}
    assert len(ids1.intersection(ids2)) == 0


def test_db_search_species_list_is_not_paged(mock_request):
    """The specimen limit pages specimens only; every matching species returns."""
    for field in ("all", "family"):
        res = TextToDbSearch(
            request=mock_request, query="nymphalidae", field=field, limit=1
        ).search()
        assert res is not None
        assert len(res["specimens"]) == 1
        assert {r["species"] for r in res["results"]} == {
            "danaus_plexippus",
            "coenonympha_pamphilus",
        }


def test_db_search_coordinate(mock_request):
    # Search for Los Angeles coordinate (34.0522, -118.2437)
    # This should match 'img1', 'img2', 'img3' (within ~100m bounding box)
    searcher = TextToDbSearch(request=mock_request, query="34.0522, -118.2437", field="coordinate")
    res = searcher.search()
    assert res is not None
    assert len(res["specimens"]) == 3
    img_ids = {s["img_id"] for s in res["specimens"]}
    assert img_ids == {"img1", "img2", "img3"}


def test_db_search_invalid_coordinate(mock_request):
    searcher = TextToDbSearch(request=mock_request, query="95.0, -118.2437", field="coordinate")
    res = searcher.search()
    assert res == {
        "query": "95.0, -118.2437",
        "results": [],
        "specimens": [],
        "total_specimens": 0,
        "page": 1,
        "limit": 50
    }


def test_api_endpoint(populated_duckdb):
    # Set up a test FastAPI app including the db_search router
    app = FastAPI()
    app.include_router(router)
    app.state.duck_db = populated_duckdb
    
    client = TestClient(app)
    response = client.get("/search/db", params={"q": "danaus plexippus", "field": "all", "page": 1, "limit": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "danaus plexippus"
    assert len(data["specimens"]) == 2
    assert data["total_specimens"] == 3
    assert data["page"] == 1
    assert data["limit"] == 2


def _pages(
    species_keys: dict[str, str] | None = None,
    image_keys: dict[str, str] | None = None,
    available: bool = True,
):
    species = species_keys or {}
    images = image_keys or {}
    pages = MagicMock()
    pages.available.return_value = available
    pages.page_keys_for_species.side_effect = lambda names: {
        n: species[n] for n in names if n in species
    }
    pages.page_keys_for_images.side_effect = lambda ids: {
        i: images[i] for i in ids if i in images
    }
    return pages


def test_species_results_link_to_valid_pages_only(mock_request):
    """A misspelling folds into its species; an unresolved name is dropped."""
    searcher = TextToDbSearch(request=mock_request, query="vanessa", field="species")
    results_df = pl.DataFrame(
        {
            "species": ["vanessa_carduii", "vanessa_cardui", "vanessa_bogus"],
            "match_field": [True, True, True],
        }
    )
    pages = _pages(
        species_keys={
            "vanessa_carduii": "vanessa_cardui",
            "vanessa_cardui": "vanessa_cardui",
        }
    )
    results = searcher._process_results(results_df, "species", ["species"], pages)
    assert [(r["species"], r["species_key"]) for r in results] == [
        ("vanessa_cardui", "vanessa_cardui")
    ]


def test_specimens_without_a_page_are_listed_unlinked(mock_request):
    searcher = TextToDbSearch(request=mock_request, query="danaus plexippus")
    full = mock_request.app.state.duck_db.conn.execute(
        "SELECT * FROM image_meta WHERE img_id IN ('img1', 'img2') ORDER BY img_id"
    ).pl()
    pages = _pages(image_keys={"img1": "danaus_plexippus"})
    specimens = searcher._process_specimens(full, "species", ["species"], pages)
    assert [(s["img_id"], s["species_key"]) for s in specimens] == [
        ("img1", "danaus_plexippus"),
        ("img2", None),
    ]


def test_without_a_run_specimens_link_to_the_recorded_binomial(mock_request):
    res = TextToDbSearch(
        request=mock_request, query="danaus plexippus", field="all"
    ).search()
    assert res is not None
    keys = {s["img_id"]: s["species_key"] for s in res["specimens"]}
    assert keys == {
        "img1": "danaus_plexippus",
        "img2": "danaus_plexippus",
        "img3": "danaus_plexippus",
    }
    assert res["results"][0]["species_key"] == "danaus_plexippus"
