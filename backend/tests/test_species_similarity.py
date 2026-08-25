"""Tests for SpeciesSimilarity and VisuallySimilarSpeciesPayload."""

import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from app.query.species_similarity import (
    SpeciesSimilarity,
    VisuallySimilarSpeciesPayload,
)


class TestVisuallySimilarSpeciesPayload:

    def test_serializes_to_camel_case(self):
        payload = VisuallySimilarSpeciesPayload(
            dorsal=[{"species": "a", "imgId": "1", "distance": 0.1}],
            ventral=[],
        )
        data = payload.model_dump(by_alias=True)
        assert "dorsal" in data
        assert "ventral" in data

    def test_empty_payload(self):
        payload = VisuallySimilarSpeciesPayload(dorsal=[], ventral=[])
        data = payload.model_dump(by_alias=True)
        assert data["dorsal"] == []
        assert data["ventral"] == []


class TestSpeciesSimilarity:

    def _make_instance(self, fake_request, limit=10):
        return SpeciesSimilarity(request=fake_request, limit=limit)

    # ------------------------------------------------------------------
    # _filter_similar_images
    # ------------------------------------------------------------------

    def test_filter_removes_query_species(self, fake_request):
        sim = self._make_instance(fake_request)
        df = pl.DataFrame({
            "imgId": ["img-001", "img-002", "img-003"],
            "species": ["danaus_plexippus", "vanessa_cardui", "vanessa_atalanta"],
            "distance": [0.0, 0.3, 0.5],
        })
        result = sim._filter_similar_images(df, "danaus plexippus")
        species_list = [r["species"] for r in result]
        assert "danaus_plexippus" not in species_list
        assert len(result) == 2

    def test_filter_handles_case_and_spaces(self, fake_request):
        """Filtering should be case-insensitive and space/underscore agnostic."""
        sim = self._make_instance(fake_request)
        df = pl.DataFrame({
            "imgId": ["img-001", "img-002"],
            "species": ["Danaus Plexippus", "Vanessa Cardui"],
            "distance": [0.0, 0.3],
        })
        result = sim._filter_similar_images(df, "Danaus Plexippus")
        assert len(result) == 1
        assert result[0]["species"] == "Vanessa Cardui"

    def test_filter_returns_empty_when_all_same_species(self, fake_request):
        sim = self._make_instance(fake_request)
        df = pl.DataFrame({
            "imgId": ["img-001"],
            "species": ["danaus_plexippus"],
            "distance": [0.0],
        })
        result = sim._filter_similar_images(df, "danaus plexippus")
        assert result == []

    # ------------------------------------------------------------------
    # _filter_by_side
    # ------------------------------------------------------------------

    def test_filter_by_side_dorsal(self, fake_request):
        sim = self._make_instance(fake_request)
        df = pl.DataFrame({
            "img_id": ["img-001", "img-002", "img-003"],
            "class_dv": ["dorsal", "ventral", "dorsal"],
        })
        result = sim._filter_by_side(df, "dorsal")
        assert result is not None
        assert len(result) == 2

    def test_filter_by_side_returns_none_when_no_match(self, fake_request):
        sim = self._make_instance(fake_request)
        df = pl.DataFrame({
            "img_id": ["img-001"],
            "class_dv": ["ventral"],
        })
        result = sim._filter_by_side(df, "dorsal")
        assert result is None

    # ------------------------------------------------------------------
    # find_similar_species (integration-ish with mocks)
    # ------------------------------------------------------------------

    @patch("app.query.species_similarity.ImagePersistData")
    @patch("app.query.species_similarity.ImageMetaService")
    def test_find_similar_species_returns_dict(self, MockMeta, MockPersist, fake_request):
        # Mock meta to return image data with dorsal/ventral
        meta_df = pl.DataFrame({
            "img_id": ["img-001", "img-002"],
            "species": ["danaus_plexippus", "danaus_plexippus"],
            "source_db": ["MCZ", "MCZ"],
            "class_dv": ["dorsal", "ventral"],
        })
        MockMeta.return_value.get_image_meta_by_species.return_value = meta_df

        # Mock ImagePersistData.find_similar_images
        similar_df = pl.DataFrame({
            "imgId": ["img-100", "img-101"],
            "species": ["vanessa_cardui", "vanessa_atalanta"],
            "distance": [0.2, 0.4],
        })
        MockPersist.return_value.find_similar_images.return_value = similar_df

        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("danaus plexippus")

        assert result is not None
        assert "dorsal" in result
        assert "ventral" in result

    @patch("app.query.species_similarity.ImageMetaService")
    def test_find_similar_species_returns_none_when_no_images(self, MockMeta, fake_request):
        MockMeta.return_value.get_image_meta_by_species.return_value = pl.DataFrame()
        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("nonexistent_species")
        assert result is None
