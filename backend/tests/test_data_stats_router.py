"""Tests for the data statistics router."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from app.main import app as main_app
from app.routers.data_stats import (
    TAXON_COUNTS_CACHE_CONTROL,
    get_embedding_distribution,
    router,
)
from app.routers.http_cache import NO_STORE


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


COUNTS = {"imageEntries": 5, "familyCount": 2}


class TestTaxonCountsEndpoint:
    """The collection summary is computed once per process and served cached.

    Each test builds its own app, since the counts are held on app.state.
    """

    @patch("app.routers.data_stats.TaxonSearch")
    def test_counts_are_computed_once(self, MockSearch):
        MockSearch.return_value.get_counts.return_value = COUNTS
        fresh = TestClient(_create_test_app())

        first = fresh.get("/stats/taxon")
        second = fresh.get("/stats/taxon")

        assert first.json() == second.json() == COUNTS
        assert first.headers["cache-control"] == TAXON_COUNTS_CACHE_CONTROL
        MockSearch.return_value.get_counts.assert_called_once()

    @patch("app.routers.data_stats.TaxonSearch")
    def test_a_failed_computation_is_retried(self, MockSearch):
        MockSearch.return_value.get_counts.side_effect = [None, COUNTS]
        fresh = TestClient(_create_test_app())

        failed = fresh.get("/stats/taxon")
        retried = fresh.get("/stats/taxon")

        assert failed.status_code == 500
        assert failed.headers["cache-control"] == NO_STORE
        assert retried.status_code == 200
        assert retried.json() == COUNTS


def test_responses_are_gzipped():
    assert any(m.cls is GZipMiddleware for m in main_app.user_middleware)
