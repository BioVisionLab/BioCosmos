# Test cases for API calls in a FastAPI application
# To test run: `uv run pytest tests` from the backend directory
from fastapi.testclient import TestClient
from app.main import app
import base64

client = TestClient(app)


# def test_image_search_empty_query():
#     response = client.get("/search/image")
#     assert response.status_code == 500
#     assert response.json() == {
#         "error": "Missing 'image' field in JSON body"
#     }


# def test_image_search_invalid_image():
#     response = client.get(
#         "/search/image", json={"image": "not_base64"}
#     )
#     assert response.status_code in (400, 500)


# def test_image_search_valid_image():
#     with open("tests/data/mcz-ent-169070_1_1.png", "rb") as f:
#         image_bytes = f.read()
#     base64_image = base64.b64encode(image_bytes).decode("utf-8")
#     response = client.post(
#         "/search/image", json={"image": base64_image}
#     )
#     assert response.status_code == 200
#     assert isinstance(response.json(), list)
