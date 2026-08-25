"""Tests for the species_data router endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.species_data import (
    router,
    get_precomputed_similarity,
    get_species_similarity,
)


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with just the species_data router."""
    app = FastAPI()
    app.include_router(router)
    return app


app = _create_test_app()
client = TestClient(app)


# =========================================================================
# GET /species/{scientific_name}/biology
# =========================================================================

class TestFetchSpeciesBiology:

    def test_empty_species_name_returns_400(self):
        response = client.get("/species/ /biology")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @patch("app.routers.species_data.TaxonSearch")
    def test_not_found_returns_404(self, MockTaxon):
        instance = MockTaxon.return_value
        instance.search = AsyncMock(return_value=None)
        response = client.get("/species/unknownspecies/biology")
        assert response.status_code == 404
        assert "message" in response.json()

    @patch("app.routers.species_data.TaxonSearch")
    def test_success_returns_200(self, MockTaxon):
        instance = MockTaxon.return_value
        instance.search = AsyncMock(return_value={"taxonomy": {"family": "Nymphalidae"}})
        response = client.get("/species/danaus_plexippus/biology")
        assert response.status_code == 200
        assert response.json()["taxonomy"]["family"] == "Nymphalidae"

    @patch("app.routers.species_data.TaxonSearch")
    def test_exception_returns_500(self, MockTaxon):
        instance = MockTaxon.return_value
        instance.search = AsyncMock(side_effect=Exception("GBIF down"))
        response = client.get("/species/danaus_plexippus/biology")
        assert response.status_code == 500


# =========================================================================
# GET /species/{scientific_name}/similar
# =========================================================================

class TestFetchVisuallySimilarSpecies:

    def test_precomputed_result_returned(self):
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [{"species": "vanessa_cardui", "imgId": "img-001", "distance": 0.1}],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/danaus_plexippus/similar")
            assert response.status_code == 200
            data = response.json()
            assert "dorsal" in data
            assert len(data["dorsal"]) == 1
            runtime.find_similar_species.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_falls_back_to_runtime(self):
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = None

        runtime = MagicMock()
        runtime.find_similar_species.return_value = {
            "dorsal": [],
            "ventral": [{"species": "vanessa_atalanta", "imgId": "img-002", "distance": 0.2}],
        }

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/danaus_plexippus/similar")
            assert response.status_code == 200
            data = response.json()
            assert len(data["ventral"]) == 1
        finally:
            app.dependency_overrides.clear()

    def test_404_when_no_results(self):
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = None

        runtime = MagicMock()
        runtime.find_similar_species.return_value = None

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/nonexistent_species/similar")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# =========================================================================
# GET /species/{scientific_name}/specimens
# =========================================================================

class TestFetchSpeciesSpecimens:

    @patch("app.routers.species_data.SpecimenData")
    def test_success(self, MockSpecimen):
        MockSpecimen.return_value.summarize.return_value = {
            "total": 5, "institutions": ["MCZ"]
        }
        response = client.get("/species/danaus_plexippus/specimens")
        assert response.status_code == 200
        assert response.json()["total"] == 5

    @patch("app.routers.species_data.SpecimenData")
    def test_not_found(self, MockSpecimen):
        MockSpecimen.return_value.summarize.return_value = None
        response = client.get("/species/nonexistent/specimens")
        assert response.status_code == 500  # Exception wraps the HTTPException


# =========================================================================
# Classification endpoints
# =========================================================================

class TestClassificationEndpoints:

    @patch("app.routers.species_data.FamilySearch")
    def test_family_classification_success(self, MockFamily):
        instance = MockFamily.return_value
        instance.get_classification = AsyncMock(
            return_value={"family": "Nymphalidae", "order": "Lepidoptera"}
        )
        response = client.get("/family/Nymphalidae/classification")
        assert response.status_code == 200
        assert response.json()["family"] == "Nymphalidae"

    @patch("app.routers.species_data.FamilySearch")
    def test_family_classification_not_found(self, MockFamily):
        instance = MockFamily.return_value
        instance.get_classification = AsyncMock(return_value=None)
        response = client.get("/family/Unknown/classification")
        assert response.status_code == 404

    @patch("app.routers.species_data.GenusSearch")
    def test_genus_classification_success(self, MockGenus):
        instance = MockGenus.return_value
        instance.get_classification = AsyncMock(
            return_value={"genus": "Danaus", "family": "Nymphalidae"}
        )
        response = client.get("/genus/Danaus/classification")
        assert response.status_code == 200

    @patch("app.routers.species_data.GenusSearch")
    def test_genus_classification_not_found(self, MockGenus):
        instance = MockGenus.return_value
        instance.get_classification = AsyncMock(return_value=None)
        response = client.get("/genus/Unknown/classification")
        assert response.status_code == 404

    @patch("app.routers.species_data.SpeciesSearch")
    def test_species_classification_success(self, MockSpecies):
        instance = MockSpecies.return_value
        instance.get_classification = AsyncMock(
            return_value={"species": "Danaus plexippus"}
        )
        response = client.get("/species/Danaus/plexippus/classification")
        assert response.status_code == 200

    @patch("app.routers.species_data.SpeciesSearch")
    def test_species_classification_not_found(self, MockSpecies):
        instance = MockSpecies.return_value
        instance.get_classification = AsyncMock(return_value=None)
        response = client.get("/species/Unknown/species/classification")
        assert response.status_code == 404
