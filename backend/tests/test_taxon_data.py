"""Tests for the species biology payload.

The behaviour under test is what happens when Catalogue of Life cannot answer.
Images, traits, specimens and literature do not come from CoL, so an
unresolved name has to leave all of them intact — returning nothing here blanks
the entire species page, which is how a missing backbone took the site down.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from app.query.taxon_data import TaxonSearch


@pytest.fixture
def search_without_backbone(memory_duckdb):
    """Search against a database that has no col_taxonomy table."""
    request = MagicMock()
    request.app.state.duck_db = memory_duckdb

    def run(query: str, method: str = "search"):
        searcher = TaxonSearch(request=request, query=query)
        return asyncio.run(getattr(searcher, method)())

    return run


class TestSearchWithoutABackbone:
    def test_returns_a_payload_rather_than_none(self, search_without_backbone):
        # None here becomes a 404, which the frontend renders as
        # "Species data not found." for the whole page.
        assert search_without_backbone("danaus_plexippus") is not None

    def test_taxonomy_is_empty_but_present(self, search_without_backbone):
        assert search_without_backbone("danaus_plexippus")["taxonomy"] == {}

    def test_the_species_id_survives(self, search_without_backbone):
        # The page still needs a name to query images and specimens with.
        assert search_without_backbone("danaus_plexippus")["speciesId"] == (
            "danaus plexippus"
        )

    def test_traits_are_still_reported(self, search_without_backbone):
        # Present as a key even when LepTraits has nothing; the biology tab
        # reads it independently of the classification.
        assert "traits" in search_without_backbone("danaus_plexippus")

    def test_an_empty_query_still_returns_none(self, search_without_backbone):
        assert search_without_backbone("   ") is None

    def test_classification_is_empty_not_an_error(self, search_without_backbone):
        assert search_without_backbone("danaus_plexippus", "get_classification") == []
