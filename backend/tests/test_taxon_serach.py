from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_taxon_search_empty_query():
    response = client.get("/taxon", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {
        "error": "Query parameter 'q' is required and cannot be empty."
    }


def test_taxon_search_no_data_found():
    response = client.get("/taxon", params={"q": "unknownspecies"})
    assert response.status_code == 404
    assert response.json() == {
        "message": "No data found for species: unknownspecies"
    }
