"""Tests for the species_data router endpoints."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.species_data import (
    router,
    get_col_search,
    get_precomputed_similarity,
    get_species_similarity,
    get_species_coordinates,
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
# GET /species/{scientific_name}/taxonomy
# =========================================================================


class TestFetchSpeciesTaxonomy:
    def _get(self, url, **lookup):
        search = MagicMock()
        search.taxonomy_detail = AsyncMock(**lookup)
        app.dependency_overrides[get_col_search] = lambda: search
        try:
            return client.get(url)
        finally:
            app.dependency_overrides.clear()

    def test_success_is_cacheable(self):
        response = self._get(
            "/species/danaus_plexippus/taxonomy",
            return_value={"nameUsages": [], "typeMaterial": []},
        )
        assert response.status_code == 200
        assert response.json()["typeMaterial"] == []
        assert "max-age" in response.headers["cache-control"]

    def test_not_found_is_not_cached(self):
        response = self._get("/species/unknown_species/taxonomy", return_value=None)
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"

    def test_error_returns_500(self):
        response = self._get(
            "/species/danaus_plexippus/taxonomy", side_effect=Exception("boom")
        )
        assert response.status_code == 500
        assert response.headers["cache-control"] == "no-store"


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

    def test_a_row_without_an_accepted_name_is_still_served(self):
        """The response model must not reject a degraded row.

        A precomputed table built before the accepted-taxon columns returns
        nulls for them; a required field there would turn that into a 500.
        """
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [
                {
                    "species": "vanessa_cardui",
                    "imgId": "img-001",
                    "distance": 0.1,
                    "acceptedName": None,
                    "acceptedRank": None,
                    "updateStatus": None,
                },
                {
                    "species": "vanessa_atalanta",
                    "imgId": "img-002",
                    "distance": 0.2,
                    "acceptedName": "Vanessa atalanta",
                    "acceptedRank": "species",
                    "updateStatus": "MATCHED",
                },
            ],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/danaus_plexippus/similar")
            assert response.status_code == 200
            dorsal = response.json()["dorsal"]
            assert dorsal[0]["acceptedName"] is None
            assert dorsal[1]["acceptedName"] == "Vanessa atalanta"
            # The recorded name stays the link target.
            assert dorsal[0]["species"] == "vanessa_cardui"
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

    def _records_its_thread(self, payload):
        """A stand-in lookup that reports whether it ran on the event loop.

        `asyncio.get_running_loop()` succeeds only when called from a thread
        that is currently running a loop. A synchronous lookup invoked inline
        from an `async def` handler runs on exactly that thread; one handed to
        `asyncio.to_thread` does not.
        """
        seen = {}

        def lookup(_scientific_name, _side=None):
            try:
                asyncio.get_running_loop()
                seen["on_event_loop"] = True
            except RuntimeError:
                seen["on_event_loop"] = False
            return payload

        return lookup, seen

    def test_precomputed_lookup_runs_off_the_event_loop(self):
        """Blocking DuckDB work must not hold the loop.

        Called inline, one slow similarity search stalled the whole server, so
        every thumbnail and metadata request the species page was waiting on
        queued behind it and the overview tab painted in pieces.
        """
        lookup, seen = self._records_its_thread({"dorsal": [], "ventral": []})
        precomputed = MagicMock()
        precomputed.find_similar_species.side_effect = lookup
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/danaus_plexippus/similar")
            assert response.status_code == 200
            assert seen["on_event_loop"] is False
        finally:
            app.dependency_overrides.clear()

    def test_runtime_lookup_runs_off_the_event_loop(self):
        """The fallback path is the slow one; it especially must not block."""
        lookup, seen = self._records_its_thread({"dorsal": [], "ventral": []})
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = None
        runtime = MagicMock()
        runtime.find_similar_species.side_effect = lookup

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            response = client.get("/species/danaus_plexippus/similar")
            assert response.status_code == 200
            assert seen["on_event_loop"] is False
        finally:
            app.dependency_overrides.clear()

    def test_a_hit_is_cacheable_and_a_miss_is_not(self):
        """Every mount of the panel re-ran the search; a hit may be reused."""
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            hit = client.get("/species/danaus_plexippus/similar")
            assert hit.status_code == 200
            assert "max-age=" in hit.headers["Cache-Control"]

            precomputed.find_similar_species.return_value = None
            runtime.find_similar_species.return_value = None
            miss = client.get("/species/nonexistent_species/similar")
            assert miss.status_code == 404
            assert miss.headers["Cache-Control"] == "no-store"
        finally:
            app.dependency_overrides.clear()

    def test_the_side_parameter_reaches_the_query_layer(self):
        """The panel's two requests must actually ask for different things."""
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            for side in ("dorsal", "ventral"):
                precomputed.find_similar_species.reset_mock()
                response = client.get(
                    f"/species/danaus_plexippus/similar?side={side}"
                )
                assert response.status_code == 200
                assert precomputed.find_similar_species.call_args.args == (
                    "danaus_plexippus",
                    side,
                )
        finally:
            app.dependency_overrides.clear()

    def test_omitting_the_side_still_asks_for_both(self):
        """The unscoped response has to stay byte-for-byte what it was."""
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            assert client.get("/species/danaus_plexippus/similar").status_code == 200
            assert precomputed.find_similar_species.call_args.args == (
                "danaus_plexippus",
                None,
            )
        finally:
            app.dependency_overrides.clear()

    def test_an_unknown_side_is_rejected(self):
        """A typo must not silently degrade to searching both sides."""
        app.dependency_overrides[get_precomputed_similarity] = lambda: MagicMock()
        app.dependency_overrides[get_species_similarity] = lambda: MagicMock()
        try:
            response = client.get("/species/danaus_plexippus/similar?side=lateral")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_the_payload_stays_camel_cased(self):
        """Returning a JSONResponse bypasses `response_model`.

        The payload model camel-cases its fields on the way out, so the
        aliasing has to be reapplied by hand or the frontend silently starts
        receiving snake_case keys.
        """
        precomputed = MagicMock()
        precomputed.find_similar_species.return_value = {
            "dorsal": [
                {
                    "species": "vanessa_cardui",
                    "imgId": "img-001",
                    "distance": 0.1,
                    "acceptedName": "Vanessa cardui",
                }
            ],
            "ventral": [],
        }
        runtime = MagicMock()

        app.dependency_overrides[get_precomputed_similarity] = lambda: precomputed
        app.dependency_overrides[get_species_similarity] = lambda: runtime

        try:
            row = client.get("/species/danaus_plexippus/similar").json()["dorsal"][0]
            assert "imgId" in row and "img_id" not in row
            assert "acceptedName" in row and "accepted_name" not in row
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


# =========================================================================
# GET /family/{family_name} and GET /genus/{genus_name}
# =========================================================================

OVERVIEW = {
    "key": "nymphalidae",
    "name": "Nymphalidae",
    "rank": "family",
    "counts": {"genusCount": 2, "speciesCount": 4, "imageCount": 9},
    "tree": [],
    "images": [],
    "sources": {"colTaxonomy": True, "harmonizedTaxonomy": True},
}


class TestHigherTaxonEndpoints:

    @patch("app.routers.species_data.FamilyOverview")
    def test_family_overview_success(self, MockFamily):
        instance = MockFamily.return_value
        instance.overview = AsyncMock(return_value=OVERVIEW)
        response = client.get("/family/Nymphalidae")
        assert response.status_code == 200
        assert response.json()["name"] == "Nymphalidae"

    @patch("app.routers.species_data.FamilyOverview")
    def test_success_is_cacheable_for_thirty_days(self, MockFamily):
        """Higher-taxon data changes only when the backend re-ingests."""
        instance = MockFamily.return_value
        instance.overview = AsyncMock(return_value=OVERVIEW)
        response = client.get("/family/Nymphalidae")
        assert "max-age=2592000" in response.headers["cache-control"]

    @patch("app.routers.species_data.FamilyOverview")
    def test_family_overview_not_found_returns_404(self, MockFamily):
        instance = MockFamily.return_value
        instance.overview = AsyncMock(return_value=None)
        response = client.get("/family/Unknown")
        assert response.status_code == 404

    @patch("app.routers.species_data.FamilyOverview")
    def test_a_missing_taxon_is_not_cached(self, MockFamily):
        """A typo must not stick in the reader's browser for a month.

        Nothing would clear it: the entry would outlive several ingestions,
        and there is no request the application could make to invalidate a
        cache that lives on someone else's machine.
        """
        instance = MockFamily.return_value
        instance.overview = AsyncMock(return_value=None)
        response = client.get("/family/Unknown")
        assert response.headers.get("cache-control") == "no-store"

    @patch("app.routers.species_data.FamilyOverview")
    def test_family_overview_error_returns_500(self, MockFamily):
        instance = MockFamily.return_value
        instance.overview = AsyncMock(side_effect=Exception("boom"))
        response = client.get("/family/Nymphalidae")
        assert response.status_code == 500
        assert response.headers.get("cache-control") == "no-store"

    @patch("app.routers.species_data.GenusOverview")
    def test_genus_overview_success(self, MockGenus):
        instance = MockGenus.return_value
        instance.overview = AsyncMock(
            return_value={
                **OVERVIEW,
                "key": "danaus",
                "name": "Danaus",
                "rank": "genus",
            }
        )
        response = client.get("/genus/Danaus")
        assert response.status_code == 200
        assert response.json()["rank"] == "genus"

    @patch("app.routers.species_data.GenusOverview")
    def test_genus_overview_not_found_returns_404(self, MockGenus):
        instance = MockGenus.return_value
        instance.overview = AsyncMock(return_value=None)
        response = client.get("/genus/Unknown")
        assert response.status_code == 404

    @patch("app.routers.species_data.FamilySearch")
    def test_the_classification_route_still_resolves(self, MockFamily):
        """The one-segment overview must not shadow the two-segment route.

        Starlette path parameters never match a slash, so it cannot — this
        pins that, because the two routes differ by one path segment and the
        failure would be silent.
        """
        instance = MockFamily.return_value
        instance.get_classification = AsyncMock(return_value={"family": "Nymphalidae"})
        response = client.get("/family/Nymphalidae/classification")
        assert response.status_code == 200
        assert response.json()["family"] == "Nymphalidae"


# =========================================================================
# GET /species/{scientific_name}/coordinates
# =========================================================================


class TestFetchSpeciesCoordinates:
    def _get(self, url, **lookup):
        service = MagicMock()
        service.get = MagicMock(**lookup)
        app.dependency_overrides[get_species_coordinates] = lambda: service
        try:
            return client.get(url), service
        finally:
            app.dependency_overrides.clear()

    def test_success_is_cacheable(self):
        payload = {"species": "danaus_plexippus", "total": 0, "truncated": False, "points": []}
        response, service = self._get(
            "/species/danaus_plexippus/coordinates", return_value=payload
        )
        assert response.status_code == 200
        assert response.json() == payload
        assert "max-age" in response.headers["cache-control"]
        service.get.assert_called_once_with("danaus_plexippus")

    def test_not_found_is_not_cached(self):
        response, _ = self._get("/species/unknown_species/coordinates", return_value=None)
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"

    def test_error_returns_500(self):
        response, _ = self._get(
            "/species/danaus_plexippus/coordinates", side_effect=Exception("boom")
        )
        assert response.status_code == 500
        assert response.headers["cache-control"] == "no-store"
