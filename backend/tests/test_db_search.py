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
