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

    @patch("app.query.species_similarity.ImagePersistData")
    @patch("app.query.species_similarity.ImageMetaService")
    def test_a_side_scoped_search_leaves_the_other_side_empty(
        self, MockMeta, MockPersist, fake_request
    ):
        """One vector scan per request instead of two.

        The panel fetches dorsal and ventral separately so each paints when it
        lands; doing that would be pointless if each request still scanned
        both sides.
        """
        meta_df = pl.DataFrame({
            "img_id": ["img-001", "img-002"],
            "species": ["danaus_plexippus", "danaus_plexippus"],
            "source_db": ["MCZ", "MCZ"],
            "class_dv": ["dorsal", "ventral"],
        })
        MockMeta.return_value.get_image_meta_by_species.return_value = meta_df
        MockPersist.return_value.find_similar_images.return_value = pl.DataFrame({
            "imgId": ["img-100"],
            "species": ["vanessa_cardui"],
            "distance": [0.2],
        })

        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("danaus plexippus", "dorsal")

        assert result["ventral"] == []
        assert len(result["dorsal"]) == 1
        assert MockPersist.return_value.find_similar_images.call_count == 1

    @patch("app.query.species_similarity.ImageMetaService")
    def test_find_similar_species_returns_none_when_no_images(self, MockMeta, fake_request):
        MockMeta.return_value.get_image_meta_by_species.return_value = pl.DataFrame()
        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("nonexistent_species")
        assert result is None


class TestResolvingToAcceptedTaxa:
    """The panel shows accepted taxa, one card each, always a full row."""

    def _make_instance(self, fake_request, resolved, limit=10):
        sim = SpeciesSimilarity(request=fake_request, limit=limit)
        sim.taxonomy = MagicMock()
        sim.taxonomy.get_for_images.return_value = resolved
        return sim

    def _record(self, img_id, key, name="Vanessa cardui", rank="species"):
        return {
            "img_id": img_id,
            "accepted_key": key,
            "display_accepted_name": name,
            "accepted_rank": rank,
            "update_status": "MATCHED" if key else "UNMATCHED",
        }

    def test_asks_the_index_for_far_more_than_it_shows(self, fake_request):
        """The index returns images; the panel wants distinct taxa."""
        sim = SpeciesSimilarity(request=fake_request, limit=10)
        assert sim.candidate_limit >= 200

        with patch(
            "app.query.species_similarity.ImagePersistData"
        ) as persist:
            persist.return_value.find_similar_images.return_value = pl.DataFrame()
            sim._get_similar_images("danaus plexippus", ["img-001"], set())

        _, kwargs = persist.return_value.find_similar_images.call_args
        assert kwargs["limit"] == sim.candidate_limit

    def test_two_spellings_of_one_taxon_make_one_card(self, fake_request):
        """And the nearest image is the one shown."""
        df = pl.DataFrame({
            "imgId": ["far", "near"],
            "species": ["vanessa_carduii", "vanessa_cardui"],
            "distance": [0.5, 0.2],
        })
        sim = self._make_instance(fake_request, {
            "far": self._record("far", "COL:2"),
            "near": self._record("near", "COL:2"),
        })
        rows = sim._resolve_accepted(df, "danaus plexippus", set())
        assert len(rows) == 1
        assert rows[0]["imgId"] == "near"
        assert rows[0]["acceptedName"] == "Vanessa cardui"

    def test_skips_what_never_resolved(self, fake_request):
        """Both a missing row and a row with no accepted taxon."""
        df = pl.DataFrame({
            "imgId": ["absent", "unmatched", "good"],
            "species": ["a_species", "b_species", "vanessa_cardui"],
            "distance": [0.1, 0.2, 0.3],
        })
        sim = self._make_instance(fake_request, {
            "unmatched": self._record("unmatched", None, None, None),
            "good": self._record("good", "COL:2"),
        })
        rows = sim._resolve_accepted(df, "danaus plexippus", set())
        assert [row["imgId"] for row in rows] == ["good"]

    def test_excludes_the_query_taxon_under_another_name(self, fake_request):
        """A senior synonym of the query species is the query species."""
        df = pl.DataFrame({
            "imgId": ["synonym", "other"],
            "species": ["danaus_archippus", "vanessa_cardui"],
            "distance": [0.1, 0.4],
        })
        sim = self._make_instance(fake_request, {
            "synonym": self._record("synonym", "COL:1", "Danaus plexippus"),
            "other": self._record("other", "COL:2"),
        })
        rows = sim._resolve_accepted(df, "danaus plexippus", {"COL:1"})
        assert [row["imgId"] for row in rows] == ["other"]

    def test_the_cut_happens_after_filtering(self, fake_request):
        """Unresolved and duplicate candidates must not consume a slot."""
        img_ids = [f"img-{i}" for i in range(30)]
        df = pl.DataFrame({
            "imgId": img_ids,
            "species": [f"species_{i}" for i in range(30)],
            "distance": [i / 100 for i in range(30)],
        })
        resolved = {}
        for i, img_id in enumerate(img_ids):
            # Only every third candidate resolves, and each to one of four taxa.
            key = f"COL:{i % 4}" if i % 3 == 0 else None
            resolved[img_id] = self._record(img_id, key, f"Taxon {i % 4}")
        sim = self._make_instance(fake_request, resolved, limit=3)
        rows = sim._resolve_accepted(df, "danaus plexippus", set())
        assert len(rows) == 3
        assert len({row["acceptedName"] for row in rows}) == 3

    def test_falls_back_to_recorded_names_without_a_run(self, fake_request):
        """A database with no harmonization still shows a panel."""
        df = pl.DataFrame({
            "imgId": ["a", "b", "c"],
            "species": ["danaus_plexippus", "vanessa_cardui", "vanessa_atalanta"],
            "distance": [0.0, 0.3, 0.5],
        })
        sim = self._make_instance(fake_request, {}, limit=1)
        rows = sim._resolve_accepted(df, "danaus plexippus", set())
        assert len(rows) == 1
        assert rows[0]["acceptedName"] is None
        assert rows[0]["species"] == "vanessa_cardui"

    def test_row_shape_is_what_the_payload_declares(self, fake_request):
        df = pl.DataFrame({
            "imgId": ["good"],
            "species": ["vanessa_cardui"],
            "distance": [0.3],
        })
        sim = self._make_instance(fake_request, {
            "good": self._record("good", "COL:2"),
        })
        rows = sim._resolve_accepted(df, "danaus plexippus", set())
        assert set(rows[0]) == {
            "imgId",
            "species",
            "distance",
            "acceptedName",
            "acceptedRank",
            "updateStatus",
        }
        # It must survive the route's response model.
        VisuallySimilarSpeciesPayload(dorsal=rows, ventral=[])



class TestOnlyComparableSpecies:
    """A card has to name a species a reader can open and compare against."""

    def _record(self, img_id, key, name, rank):
        return {
            "img_id": img_id,
            "accepted_key": key,
            "display_accepted_name": name,
            "accepted_rank": rank,
            "update_status": "MATCHED",
        }

    def _resolve(self, fake_request, frame, resolved):
        sim = SpeciesSimilarity(request=fake_request, limit=10)
        sim.taxonomy = MagicMock()
        sim.taxonomy.get_for_images.return_value = resolved
        return sim._resolve_accepted(frame, "danaus plexippus", set())

    def test_drops_a_match_that_stopped_at_genus(self, fake_request):
        """There is no species page for a genus, so the card led nowhere."""
        frame = pl.DataFrame({
            "imgId": ["genus-only", "good"],
            "species": ["vanessa", "vanessa_cardui"],
            "distance": [0.1, 0.3],
        })
        rows = self._resolve(fake_request, frame, {
            "genus-only": self._record("genus-only", "vanessa", "Vanessa", "genus"),
            "good": self._record("good", "vanessa_cardui", "Vanessa cardui", "species"),
        })
        assert [row["imgId"] for row in rows] == ["good"]

    def test_drops_a_one_word_name_whatever_its_rank_says(self, fake_request):
        """The rank column is not always right; a single word is a genus."""
        frame = pl.DataFrame({
            "imgId": ["bare", "good"],
            "species": ["vanessa", "vanessa_cardui"],
            "distance": [0.1, 0.3],
        })
        rows = self._resolve(fake_request, frame, {
            "bare": self._record("bare", "vanessa", "Vanessa", "species"),
            "good": self._record("good", "vanessa_cardui", "Vanessa cardui", "species"),
        })
        assert [row["imgId"] for row in rows] == ["good"]

    def test_keeps_a_subspecies(self, fake_request):
        """A trinomial still names a species; only the epithet is extra."""
        frame = pl.DataFrame({
            "imgId": ["ssp"],
            "species": ["vanessa_cardui_kershawi"],
            "distance": [0.1],
        })
        rows = self._resolve(fake_request, frame, {
            "ssp": self._record(
                "ssp", "vanessa_cardui", "Vanessa cardui", "subspecies"
            ),
        })
        assert [row["imgId"] for row in rows] == ["ssp"]

    def test_the_unharmonized_fallback_drops_genus_only_records(
        self, fake_request
    ):
        """With no run loaded the recorded name is all there is to judge on."""
        frame = pl.DataFrame({
            "imgId": ["genus-only", "good"],
            "species": ["vanessa", "vanessa_cardui"],
            "distance": [0.1, 0.3],
        })
        sim = SpeciesSimilarity(request=fake_request, limit=10)
        sim.taxonomy = MagicMock()
        # No harmonization run has been loaded.
        sim.taxonomy.get_for_images.return_value = {}
        rows = sim._resolve_accepted(frame, "danaus plexippus", set())
        assert [row["imgId"] for row in rows] == ["good"]
