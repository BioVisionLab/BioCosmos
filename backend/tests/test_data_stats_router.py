"""Tests for the data statistics router."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.routers.data_stats import get_embedding_distribution, router


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


app = _create_test_app()
client = TestClient(app)


SAMPLE_PAYLOAD = {
    "distributions": [
        {
            "embeddingModel": "CLIP",
            "dimensions": 512,
            "imageCount": 5000,
            "sampleSize": 2560000,
            "minimum": -2.5,
            "q1": -0.3,
            "median": 0.0,
            "q3": 0.3,
            "maximum": 2.5,
            "lowerWhisker": -1.2,
            "upperWhisker": 1.2,
            "mean": 0.0,
            "stdDev": 0.45,
        },
        {
            "embeddingModel": "UNICOM",
            "dimensions": 768,
            "imageCount": 5000,
            "sampleSize": 3840000,
            "minimum": -1.8,
            "q1": -0.2,
            "median": 0.01,
            "q3": 0.2,
            "maximum": 1.8,
            "lowerWhisker": -0.8,
            "upperWhisker": 0.8,
            "mean": 0.01,
            "stdDev": 0.3,
        },
    ]
}


# ===========================================================================
# GET /stats/embeddings
# ===========================================================================

class TestEmbeddingStatsEndpoint:
    def test_returns_distributions(self):
        service = MagicMock()
        service.get_distributions.return_value = SAMPLE_PAYLOAD
        app.dependency_overrides[get_embedding_distribution] = lambda: service
        try:
            response = client.get("/stats/embeddings")
            assert response.status_code == 200
            body = response.json()
            assert [d["embeddingModel"] for d in body["distributions"]] == [
                "CLIP",
                "UNICOM",
            ]
        finally:
            app.dependency_overrides.clear()

    def test_missing_data_returns_404(self):
        service = MagicMock()
        service.get_distributions.return_value = None
        app.dependency_overrides[get_embedding_distribution] = lambda: service
        try:
            response = client.get("/stats/embeddings")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_service_error_returns_500(self):
        service = MagicMock()
        service.get_distributions.side_effect = RuntimeError("boom")
        app.dependency_overrides[get_embedding_distribution] = lambda: service
        try:
            response = client.get("/stats/embeddings")
            assert response.status_code == 500
            assert "boom" in response.json()["message"]
        finally:
            app.dependency_overrides.clear()
