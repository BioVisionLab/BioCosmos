"""Tests for PrecomputedSpeciesSimilarity."""

import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from app.query.precomputed_similarity import PrecomputedSpeciesSimilarity


class TestPrecomputedSpeciesSimilarity:
    """Unit tests for precomputed similarity lookups."""

    def _make_instance(self, fake_request, limit=10, resolved=None):
        sim = PrecomputedSpeciesSimilarity(request=fake_request, limit=limit)
        sim.taxonomy = MagicMock()
        sim.taxonomy.get_for_images.return_value = resolved or {}
        sim.taxonomy.accepted_keys_for_species.return_value = set()
        return sim

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

    # ------------------------------------------------------------------
    # Resolving the stored recorded names
    # ------------------------------------------------------------------

    def _rows(self, duck, rows):
        """Serve `rows` as the dorsal side, nothing as the ventral."""

        def query(_query, params):
            return pl.DataFrame(rows) if params[1] == "dorsal" else pl.DataFrame()

        duck.execute_prepared_to_pl = query

    def _record(self, img_id, key, name="Vanessa cardui", rank="species"):
        return {
            "img_id": img_id,
            "accepted_key": key,
            "display_accepted_name": name,
            "accepted_rank": rank,
            "update_status": "MATCHED" if key else "UNMATCHED",
        }

    def test_serves_the_accepted_name_for_a_recorded_one(self, fake_request):
        """The stored table keeps recorded names; resolution happens here."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        self._rows(duck, [
            {"species": "vanessa_carduii", "imgId": "img-001", "distance": 0.12},
        ])
        sim = self._make_instance(fake_request, resolved={
            "img-001": self._record("img-001", "COL:2"),
        })

        row = sim.find_similar_species("danaus plexippus")["dorsal"][0]

        assert row["acceptedName"] == "Vanessa cardui"
        # The link target stays the name the images are filed under.
        assert row["species"] == "vanessa_carduii"

    def test_spellings_of_one_taxon_collapse_to_one_card(self, fake_request):
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        self._rows(duck, [
            {"species": "vanessa_carduii", "imgId": "far", "distance": 0.5},
            {"species": "vanessa_cardui", "imgId": "near", "distance": 0.2},
        ])
        sim = self._make_instance(fake_request, resolved={
            "far": self._record("far", "COL:2"),
            "near": self._record("near", "COL:2"),
        })

        dorsal = sim.find_similar_species("danaus plexippus")["dorsal"]

        assert len(dorsal) == 1
        assert dorsal[0]["imgId"] == "near"

    def test_a_subspecies_of_the_query_is_excluded(self, fake_request):
        """The stored rows only exclude the exact recorded name."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        self._rows(duck, [
            {
                "species": "danaus_plexippus_portoricensis",
                "imgId": "sub",
                "distance": 0.1,
            },
            {"species": "vanessa_cardui", "imgId": "other", "distance": 0.4},
        ])
        sim = self._make_instance(fake_request, resolved={
            "sub": self._record("sub", "COL:1", "Danaus plexippus"),
            "other": self._record("other", "COL:2"),
        })
        sim.taxonomy.accepted_keys_for_species.return_value = {"COL:1"}

        dorsal = sim.find_similar_species("danaus plexippus")["dorsal"]

        assert [row["imgId"] for row in dorsal] == ["other"]

    def test_unresolved_rows_are_skipped(self, fake_request):
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        self._rows(duck, [
            {"species": "bogus_name", "imgId": "unmatched", "distance": 0.1},
            {"species": "vanessa_cardui", "imgId": "good", "distance": 0.4},
        ])
        sim = self._make_instance(fake_request, resolved={
            "unmatched": self._record("unmatched", None, None, None),
            "good": self._record("good", "COL:2"),
        })

        dorsal = sim.find_similar_species("danaus plexippus")["dorsal"]

        assert [row["imgId"] for row in dorsal] == ["good"]

    def test_without_a_run_it_serves_the_recorded_names(self, fake_request):
        """A database with no harmonization still shows a panel."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        self._rows(duck, [
            {"species": "vanessa_cardui", "imgId": "img-001", "distance": 0.12},
        ])
        sim = self._make_instance(fake_request, resolved={})

        row = sim.find_similar_species("danaus plexippus")["dorsal"][0]

        assert row["acceptedName"] is None
        assert row["species"] == "vanessa_cardui"

    def test_every_stored_row_is_read_not_the_first_limit(self, fake_request):
        """Resolving shrinks the list, so the cut cannot happen in SQL."""
        duck = fake_request.app.state.duck_db
        duck.execute = MagicMock(return_value=MagicMock(fetchone=lambda: (1,)))
        captured = []

        def query(sql, params):
            captured.append((sql, params))
            return pl.DataFrame()

        duck.execute_prepared_to_pl = query
        self._make_instance(fake_request).find_similar_species("danaus plexippus")

        sql, params = captured[0]
        assert "LIMIT" not in sql.upper()
        assert params == ["danaus_plexippus", "dorsal"]

