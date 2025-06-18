from fastapi.testclient import TestClient
from app.main import app  # Adjust the import path to your FastAPI app

client = TestClient(app)

def test_image_search_empty_query():
    response = client.get("/img-search", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {"error": "Query parameter 'q' is required and cannot be empty."}

def test_text_search_empty_query():
    response = client.get("/text-search", params={"q": ""})
    assert response.status_code == 400
    assert response.json() == {"error": "Query parameter 'q' is required and cannot be empty."}

def test_image_search_valid_query():
    response = client.get("/img-search", params={"q": "example"})
    assert response.status_code == 200
    assert response.json() == {"query": "example", "results": []}

def test_text_search_valid_query():
    response = client.get("/text-search", params={"q": "example"})
    assert response.status_code == 200
    assert response.json() == {"query": "example", "results": []} # Assuming the embedding is returned
