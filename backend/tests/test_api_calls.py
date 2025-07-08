# Test cases for API calls in a FastAPI application
# To tes run: uv run -m pytest
from fastapi.testclient import TestClient
from app.main import app  # Adjust the import path to your FastAPI app

client = TestClient(app)


def test_image_search_empty_query():
    response = client.get("/img-search", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {
        "error": "Query parameter 'q' is required and cannot be empty."
    }


def test_text_search_empty_query():
    response = client.get("/text-search", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {
        "error": "Query parameter 'q' is required and cannot be empty."
    }


def test_image_search_valid_query():
    response = client.get("/img-search", params={"q": "example"})
    assert response.status_code == 200


def test_text_search_valid_query():
    response = client.get("/text-search", params={"q": "example"})
    assert response.status_code == 200


def test_taxon_search_empty_query():
    response = client.get("/taxon", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {"detail": "Species name is required"}


def test_taxon_search_valid_query():
    response = client.get("/taxon", params={"q": "example"})
    assert response.status_code == 200
    assert response.json() == {
        "query": "example",
        "results": [],
    }  # Assuming the embedding is returned


def test_taxon_search_valid_species():
    response = client.get("/taxon", params={"q": "Danaus plexippus"})
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert isinstance(
        data["results"], list
    )  # Assuming results is a list
    # Further checks can be added based on expected structure of results
