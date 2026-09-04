"""Tests for the image_retrieval router's paged species image-ID endpoint."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.image_retrieval import (
    DEFAULT_IMAGE_ID_LIMIT,
    MAX_IMAGE_ID_LIMIT,
    router,
)


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with just the image_retrieval router."""
    app = FastAPI()
    app.include_router(router)
    return app


app = _create_test_app()
client = TestClient(app)


# =========================================================================
# GET /image/{scientific_name}/metadata
# =========================================================================

class TestFetchSpeciesImageIds:

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_defaults_applied_when_params_absent(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = ["a", "b"]

        response = client.get("/image/danaus_plexippus/metadata")

        assert response.status_code == 200
        assert response.json() == ["a", "b"]
        MockRetrieval.return_value.get_species_image_ids.assert_called_once_with(
            "danaus_plexippus", limit=DEFAULT_IMAGE_ID_LIMIT, offset=0
        )

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_explicit_limit_and_offset_reach_query_layer(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = ["c"]

        response = client.get(
            "/image/danaus_plexippus/metadata", params={"limit": 24, "offset": 48}
        )

        assert response.status_code == 200
        MockRetrieval.return_value.get_species_image_ids.assert_called_once_with(
            "danaus_plexippus", limit=24, offset=48
        )

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_limit_clamped_to_upper_bound(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = ["a"]

        client.get("/image/danaus_plexippus/metadata", params={"limit": 100_000})

        _, kwargs = MockRetrieval.return_value.get_species_image_ids.call_args
        assert kwargs["limit"] == MAX_IMAGE_ID_LIMIT

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_limit_clamped_to_lower_bound(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = ["a"]

        client.get("/image/danaus_plexippus/metadata", params={"limit": 0})

        _, kwargs = MockRetrieval.return_value.get_species_image_ids.call_args
        assert kwargs["limit"] == 1

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_negative_offset_clamped_to_zero(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = ["a"]

        client.get("/image/danaus_plexippus/metadata", params={"offset": -5})

        _, kwargs = MockRetrieval.return_value.get_species_image_ids.call_args
        assert kwargs["offset"] == 0

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_empty_first_page_returns_404(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = []

        response = client.get("/image/unknown_species/metadata")

        assert response.status_code == 404

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_paging_past_the_end_returns_empty_list(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.return_value = []

        response = client.get(
            "/image/danaus_plexippus/metadata", params={"limit": 24, "offset": 9600}
        )

        assert response.status_code == 200
        assert response.json() == []

    @patch("app.routers.image_retrieval.ImageMetaRetrieval")
    def test_query_layer_failure_returns_500(self, MockRetrieval):
        MockRetrieval.return_value.get_species_image_ids.side_effect = RuntimeError(
            "duckdb exploded"
        )

        response = client.get("/image/danaus_plexippus/metadata")

        assert response.status_code == 500
