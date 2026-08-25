"""Tests for PrecomputedSpeciesSimilarity."""

import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from app.query.precomputed_similarity import PrecomputedSpeciesSimilarity


class TestPrecomputedSpeciesSimilarity:
    """Unit tests for precomputed similarity lookups."""

    def _make_instance(self, fake_request, limit=10):
        return PrecomputedSpeciesSimilarity(request=fake_request, limit=limit)

    # ------------------------------------------------------------------
    # Table existence
    # ------------------------------------------------------------------

    def test_returns_none_when_table_missing(self, fake_request):
        """Should return None when the similarity table doesn't exist."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (0,))
        )
        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("Danaus plexippus")
        assert result is None

    def test_returns_none_when_table_check_raises(self, fake_request):
        """Should gracefully return None if the table check throws."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(side_effect=Exception("connection lost"))
        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("Danaus plexippus")
        assert result is None

    # ------------------------------------------------------------------
    # Species name normalization
    # ------------------------------------------------------------------

    def test_species_name_normalized(self, fake_request):
        """Spaces → underscores, lowered, stripped."""
        duck = fake_request.app.state.duck_db
        # Table exists
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (1,))
        )

        captured_params = []

        def capture_prepared(query, params):
            captured_params.append(params)
            return pl.DataFrame()

        duck.execute_prepared_to_pl = capture_prepared

        sim = self._make_instance(fake_request)
        sim.find_similar_species("  Danaus Plexippus  ")

        # Two calls: dorsal + ventral
        assert len(captured_params) == 2
        for params in captured_params:
            assert params[0] == "danaus_plexippus"

    # ------------------------------------------------------------------
    # Successful result
    # ------------------------------------------------------------------

    def test_returns_payload_with_dorsal_and_ventral(self, fake_request):
        """Should return a dict with dorsal and ventral keys on success."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (1,))
        )

        dorsal_df = pl.DataFrame({
            "species": ["vanessa_cardui"],
            "imgId": ["img-001"],
            "distance": [0.12],
        })
        ventral_df = pl.DataFrame({
            "species": ["vanessa_atalanta"],
            "imgId": ["img-002"],
            "distance": [0.15],
        })

        call_count = {"n": 0}

        def side_effect(query, params):
            call_count["n"] += 1
            if params[1] == "dorsal":
                return dorsal_df
            return ventral_df

        duck.execute_prepared_to_pl = side_effect

        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("danaus plexippus")

        assert result is not None
        assert "dorsal" in result
        assert "ventral" in result
        assert len(result["dorsal"]) == 1
        assert result["dorsal"][0]["species"] == "vanessa_cardui"

    def test_returns_none_when_both_sides_empty(self, fake_request):
        """Should return None when no dorsal or ventral results exist."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (1,))
        )
        duck.execute_prepared_to_pl = MagicMock(return_value=pl.DataFrame())

        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("unknown species")
        assert result is None

    def test_returns_payload_when_only_dorsal(self, fake_request):
        """Should still return a payload when only dorsal has results."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (1,))
        )

        dorsal_df = pl.DataFrame({
            "species": ["vanessa_cardui"],
            "imgId": ["img-001"],
            "distance": [0.12],
        })

        def side_effect(query, params):
            if params[1] == "dorsal":
                return dorsal_df
            return pl.DataFrame()

        duck.execute_prepared_to_pl = side_effect

        sim = self._make_instance(fake_request)
        result = sim.find_similar_species("danaus plexippus")
        assert result is not None
        assert len(result["dorsal"]) == 1
        assert result["ventral"] == []

    # ------------------------------------------------------------------
    # Limit
    # ------------------------------------------------------------------

    def test_limit_passed_to_query(self, fake_request):
        """Custom limit should be forwarded to the SQL query."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(
            return_value=MagicMock(fetchone=lambda: (1,))
        )

        captured_limits = []

        def capture(query, params):
            captured_limits.append(params[2])
            return pl.DataFrame()

        duck.execute_prepared_to_pl = capture

        sim = self._make_instance(fake_request, limit=5)
        sim.find_similar_species("danaus plexippus")
        assert all(lim == 5 for lim in captured_limits)
