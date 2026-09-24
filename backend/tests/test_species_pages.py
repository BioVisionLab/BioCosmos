"""Tests for choosing the species page a record links to.

Run against a real in-memory DuckDB, because the behaviour under test is the
SQL: which recorded spelling wins for a species, and which records have no
page at all.
"""

import polars as pl
import pytest

from app.services.species_pages import SpeciesPageResolver

# img_id -> (recorded species, update_status, accepted_species_name)
RECORDS = {
    "a1": ("coenonympha_pamphilus", "MATCHED", "Coenonympha pamphilus"),
    "a2": ("coenonympha_pamphilus", "MATCHED", "Coenonympha pamphilus"),
    # A misspelling of the same species: it has a page of its own, but an
    # orphaned one, and should link to the species' page instead.
    "a3": ("coenonympha_pamfilus", "MATCHED", "Coenonympha pamphilus"),
    # Mostly filed under a trinomial, which the binomial route cannot reach.
    "b1": ("vanessa_cardui_cardui", "MATCHED", "Vanessa cardui"),
    "b2": ("vanessa_cardui_cardui", "MATCHED", "Vanessa cardui"),
    "b3": ("vanessa_cardui", "MATCHED", "Vanessa cardui"),
    # Filed only under a trinomial: no page a link can reach.
    "c1": ("danaus_plexippus_plexippus", "MATCHED", "Danaus plexippus"),
    # Resolved to genus rank only.
    "d1": ("coenonympha", "MATCHED", None),
    # Never resolved.
    "e1": ("unresolvable_name", "UNMATCHED", None),
}


def _install(client) -> None:
    images = pl.DataFrame(
        [
            {"img_id": img_id, "species": species, "class_dv": "dorsal"}
            for img_id, (species, _, _) in RECORDS.items()
        ]
    )
    taxonomy = pl.DataFrame(
        [
            {
                "img_id": img_id,
                "update_status": status,
                "accepted_name": accepted
                or ("Coenonympha" if img_id == "d1" else None),
                "accepted_species_name": accepted,
                "accepted_family": "Nymphalidae",
            }
            for img_id, (_, status, accepted) in RECORDS.items()
        ],
        schema_overrides={
            "accepted_name": pl.Utf8,
            "accepted_species_name": pl.Utf8,
        },
    )
    client.register("seed_images", images)
    client.execute("CREATE TABLE image_meta AS SELECT * FROM seed_images")
    client.register("seed_taxonomy", taxonomy)
    client.execute("CREATE TABLE image_meta_taxonomy AS SELECT * FROM seed_taxonomy")


@pytest.fixture
def resolver(memory_duckdb):
    _install(memory_duckdb)
    return SpeciesPageResolver(memory_duckdb)


class TestPageKeysForImages:
    def test_an_accepted_record_links_to_its_own_spelling(self, resolver):
        assert resolver.page_keys_for_images(["a1"]) == {"a1": "coenonympha_pamphilus"}

    def test_a_misspelling_links_to_the_species_page(self, resolver):
        assert resolver.page_keys_for_images(["a3"]) == {"a3": "coenonympha_pamphilus"}

    def test_a_binomial_spelling_wins_over_a_commoner_trinomial(self, resolver):
        keys = resolver.page_keys_for_images(["b1", "b2", "b3"])
        assert set(keys.values()) == {"vanessa_cardui"}
        assert set(keys) == {"b1", "b2", "b3"}

    @pytest.mark.parametrize(
        "img_id",
        [
            # Only ever filed under a trinomial.
            "c1",
            # Resolved to a genus, not a species.
            "d1",
            # Never resolved.
            "e1",
            # Not in the collection.
            "zz",
        ],
    )
    def test_records_without_a_valid_page_are_absent(self, resolver, img_id):
        assert resolver.page_keys_for_images([img_id]) == {}

    def test_empty_input_runs_no_query(self, resolver):
        assert resolver.page_keys_for_images([]) == {}


class TestPageKeysForSpecies:
    def test_names_resolve_whatever_their_spelling(self, resolver):
        keys = resolver.page_keys_for_species(
            ["Coenonympha pamfilus", "vanessa_cardui_cardui", "unresolvable_name"]
        )
        assert keys == {
            "Coenonympha pamfilus": "coenonympha_pamphilus",
            "vanessa_cardui_cardui": "vanessa_cardui",
        }

    def test_a_trinomial_only_species_has_no_page(self, resolver):
        assert resolver.page_keys_for_species(["danaus_plexippus_plexippus"]) == {}


class TestWithoutAHarmonizationRun:
    def test_nothing_resolves_and_it_says_so(self, memory_duckdb):
        resolver = SpeciesPageResolver(memory_duckdb)
        assert resolver.available() is False
        assert resolver.page_keys_for_images(["a1"]) == {}
        assert resolver.page_keys_for_species(["coenonympha_pamphilus"]) == {}
