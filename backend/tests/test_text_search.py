# Test cases for API calls in a FastAPI application
# To test run: `uv run pytest tests` from the backend directory
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_text_search_valid_query():
    response = client.get("/text-search", params={"q": "example"})
    assert response.status_code == 200


def test_taxon_search_valid_species():
    response = client.get("/taxon", params={"q": "Danaus plexippus"})
    assert response.status_code == 200
    data = response.json()
    assert "speciesId" in data
    assert "taxonomy" in data
    assert isinstance(
        data["taxonomy"], dict
    )  # Assuming taxonomy is a dict
    # Further checks can be added based on expected structure of taxonomy
    assert "class" in data["taxonomy"]
    assert "family" in data["taxonomy"]
    assert "authorship" in data["taxonomy"]
