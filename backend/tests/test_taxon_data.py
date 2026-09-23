"""Tests for the species biology payload.

The behaviour under test is what happens when Catalogue of Life cannot answer.
Images, traits, specimens and literature do not come from CoL, so an
unresolved name has to leave all of them intact — returning nothing here blanks
the entire species page, which is how a missing backbone took the site down.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from app.query.taxon_data import TaxonSearch, TaxonStatPayload


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


class TestTaxonStatPayloadDefaults:
    """A missing colharmonize run or GBIF join must not blank the whole page.

    Every counting service returns None when its source table is absent, so
    the payload has to turn that into a reportable zero/empty value rather
    than raising or serializing null.
    """

    def test_missing_validation_data_defaults_to_zero_and_empty(self):
        payload = TaxonStatPayload.from_data(
            gbif_entries=None,
            lep_traits_entries=None,
            image_entries=None,
            family_count=None,
            family_count_validated=None,
            species_count=None,
            source_db_count=None,
            entries_by_family=None,
            entries_by_family_validated=None,
            institution_counts=None,
            top_ten_species={},
        )
        assert payload.familyCountValidated == 0
        assert payload.entriesByFamilyValidated == {}
        assert payload.institutionCounts == {}
        assert payload.model_dump()["institutionDirectory"] == {}

    def test_present_validation_data_survives_untouched(self):
        payload = TaxonStatPayload.from_data(
            gbif_entries=10,
            lep_traits_entries=5,
            image_entries=100,
            family_count=7,
            family_count_validated=9,
            species_count=20,
            source_db_count={"gbif": 100},
            entries_by_family={"nymphalidae": 60},
            entries_by_family_validated={"Nymphalidae": 58},
            institution_counts={"NHMUK": 40, "Unknown": 60},
            top_ten_species={"danaus_plexippus": 30},
        )
        assert payload.familyCountValidated == 9
        assert payload.entriesByFamilyValidated == {"Nymphalidae": 58}
        assert payload.institutionCounts == {"NHMUK": 40, "Unknown": 60}

    def test_institution_directory_serializes_by_code(self):
        payload = TaxonStatPayload.from_data(
            gbif_entries=1,
            lep_traits_entries=1,
            image_entries=1,
            family_count=1,
            family_count_validated=1,
            species_count=1,
            source_db_count=None,
            entries_by_family=None,
            entries_by_family_validated=None,
            institution_counts={"NHMUK": 1},
            top_ten_species={},
            institution_directory={
                "NHMUK": {
                    "name": "Natural History Museum, London",
                    "homepage": "http://www.nhm.ac.uk/",
                    "country": "GB",
                    "source": "grscicoll_verified",
                }
            },
        )
        assert payload.model_dump()["institutionDirectory"]["NHMUK"] == {
            "name": "Natural History Museum, London",
            "homepage": "http://www.nhm.ac.uk/",
            "country": "GB",
            "source": "grscicoll_verified",
        }
