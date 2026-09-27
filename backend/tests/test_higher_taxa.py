"""Tests for the order, family and genus page data.

These run against a real in-memory DuckDB with the miniature Catalogue of Life
release actually ingested, because the behaviour under test *is* the SQL:
which images count towards a taxon, which genus a renamed species lands in,
and which usage wins when two families share a genus name. A fake client
returning empty frames would assert nothing about any of that.

`build_tree` is the exception — it is a pure function over member rows and is
tested with no database at all.
"""

import os
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import polars as pl
import pytest
from fastapi import Request

from app.query import higher_taxa as higher_taxa_query
from app.query.higher_taxa import (
    PAYLOAD_CACHE,
    UNPLACED_KEY,
    HigherTaxonCounts,
    HigherTaxonOverview,
    OrderOverview,
    TaxonNode,
    attach_family_images,
    build_order_tree,
    build_rooted_tree,
    build_tree,
)
from app.services.col import ColBackboneService
from app.services.higher_taxa import HigherTaxonRepository

# Only the columns the higher-taxon queries actually read. `species` is stored
# lowercase and underscored, as the real collection stores it.
IMAGES = [
    ("i0", "coenonympha_pamphilus", "ventral"),
    ("i1", "coenonympha_pamphilus", "dorsal"),
    ("i2", "coenonympha_pamphilus", "ventral"),
    ("i3", "aphantopus_hyperantus", "dorsal"),
    ("i4", "aphantopus_hyperantus", "ventral"),
    ("i5", "zzzonympha_pamphilus", "dorsal"),
    # Recorded under a name Catalogue of Life has since moved.
    ("i6", "oldgenus_renamed", "dorsal"),
    # Never resolved by the harmonization run.
    ("i7", "unresolvable_name", "dorsal"),
    # Identified only to genus: an image of a specimen, but not of a species,
    # so it counts nowhere.
    ("i8", "coenonympha", "dorsal"),
    # A genus the backbone knows nothing about.
    ("i9", "nosuchgenus_ghost", "dorsal"),
    # A subspecies of a species the collection also holds: one species to a
    # reader, and one tile.
    ("i10", "coenonympha_pamphilus_lyllus", "dorsal"),
    # A genus held only through a genus-rank match, as `allancastria_cerisyi`
    # is: counting it would list a genus whose own page has no species.
    ("i11", "onlygenus_misspeltus", "dorsal"),
]

# img_id -> (update_status, accepted_name, accepted_family)
TAXONOMY = {
    "i0": ("MATCHED", "Coenonympha pamphilus", "Nymphalidae"),
    "i1": ("MATCHED", "Coenonympha pamphilus", "Nymphalidae"),
    "i2": ("MATCHED", "Coenonympha pamphilus", "Nymphalidae"),
    "i3": ("MATCHED", "Aphantopus hyperantus", "Nymphalidae"),
    "i4": ("MATCHED", "Aphantopus hyperantus", "Nymphalidae"),
    "i5": ("MATCHED", "Zzzonympha pamphilus", "Nymphalidae"),
    "i6": ("MATCHED", "Coenonympha tullia", "Nymphalidae"),
    "i7": ("UNMATCHED", None, None),
    "i8": ("MATCHED", "Coenonympha", "Nymphalidae"),
    "i9": ("MATCHED", "Nosuchgenus ghost", "Nymphalidae"),
    "i10": ("MATCHED", "Coenonympha pamphilus", "Nymphalidae"),
    "i11": ("MATCHED", "Onlygenus", "Nymphalidae"),
}


def _install_collection(client) -> None:
    images = pl.DataFrame(
        [
            {
                "img_id": img_id,
                "species": species,
                "family": "nymphalidae",
                "class_dv": class_dv,
            }
            for img_id, species, class_dv in IMAGES
        ]
    )
    taxonomy = pl.DataFrame(
        [
            {
                "img_id": img_id,
                "update_status": status,
                "accepted_name": accepted,
                # colharmonize leaves this empty for a match that only
                # reached genus rank, which is what makes such a record an
                # image without a species.
                "accepted_species_name": (
                    accepted if accepted and " " in accepted else None
                ),
                "display_accepted_name": accepted,
                "accepted_family": family,
            }
            for img_id, (status, accepted, family) in TAXONOMY.items()
        ]
    )
    client.register("seed_images", images)
    client.execute("CREATE TABLE image_meta AS SELECT * FROM seed_images")
    client.register("seed_taxonomy", taxonomy)
    client.execute("CREATE TABLE image_meta_taxonomy AS SELECT * FROM seed_taxonomy")


@pytest.fixture
def repository(memory_duckdb, col_fixture_dir):
    """A repository over an ingested backbone and a small collection."""
    backbone = ColBackboneService.__new__(ColBackboneService)
    backbone.db_client = memory_duckdb
    backbone.path = os.path.join(col_fixture_dir, "NameUsage.tsv")
    backbone.vernacular_path = os.path.join(col_fixture_dir, "VernacularName.tsv")
    backbone.table = "col_taxonomy"
    backbone.vernacular_table = "col_vernacular"
    backbone.clade_rank = "order"
    backbone.clade_value = "Lepidoptera"
    backbone.skip_ingestion = False
    backbone._ingest_name_usage()
    backbone._ingest_vernacular_names()

    _install_collection(memory_duckdb)
    return _repository(memory_duckdb)


@pytest.fixture
def repository_without_backbone(memory_duckdb):
    """The same collection with no Catalogue of Life ingested."""
    _install_collection(memory_duckdb)
    return _repository(memory_duckdb)


def _repository(client) -> HigherTaxonRepository:
    repository = HigherTaxonRepository.__new__(HigherTaxonRepository)
    repository.db_client = client
    repository.image_meta_table = "image_meta"
    repository.col_table = "col_taxonomy"
    repository.status_table = "image_meta_taxonomy"
    repository._col_present = None
    repository._status_present = None
    return repository


def by_key(rows: list[dict], field: str) -> dict:
    return {row[field]: row for row in rows}


class TestFamilyMembers:
    def test_rolls_images_up_to_the_accepted_genus(self, repository):
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert set(genera) == {
            "coenonympha",
            "aphantopus",
            "zzzonympha",
            "nosuchgenus",
        }

    def test_a_renamed_species_counts_under_its_new_genus(self, repository):
        """`oldgenus_renamed` resolves to Coenonympha tullia, so it belongs there.

        Membership follows the accepted name, which is the whole point of
        harmonizing: a species Catalogue of Life moved appears where Catalogue
        of Life now puts it, not where the label happened to say.
        """
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert genera["coenonympha"]["species_count"] == 2
        assert "oldgenus" not in genera

    def test_unmatched_images_are_excluded(self, repository):
        """Strict membership: an image not resolved to a species counts nowhere."""
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert "unresolvable" not in genera
        total = sum(row["image_count"] for row in genera.values())
        # Every image but the unresolved one and the two genus-only ones.
        assert total == len(IMAGES) - 3

    def test_a_genus_only_record_is_not_counted(self, repository):
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        # Three pamphilus images, one of its subspecies, one renamed; the one
        # identified only to genus is not an image of a valid species.
        assert genera["coenonympha"]["image_count"] == 5
        # Two species among them: the subspecies is not a third.
        assert genera["coenonympha"]["species_count"] == 2

    def test_a_genus_held_only_to_genus_rank_is_not_listed(self, repository):
        """Listing it would link to a genus page that has no species: a 404."""
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert "onlygenus" not in genera
        assert repository.genus_members("onlygenus") == []

    def test_places_a_genus_under_its_col_subfamily_and_tribe(self, repository):
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert genera["aphantopus"]["subfamily"] == "Satyrinae"
        assert genera["aphantopus"]["tribe"] == "Coenonymphini"

    def test_prefers_the_homonym_in_the_family_being_rendered(self, repository):
        """Two families accept a genus called Zzzonympha; this page wants ours.

        Without the dedupe this row would either multiply or resolve to the
        Erebidae usage and be filed as belonging to another family.
        """
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert genera["zzzonympha"]["col_id"] == "GEN2"
        assert genera["zzzonympha"]["col_family"] == "nymphalidae"

    def test_a_genus_absent_from_col_still_appears(self, repository):
        genera = by_key(repository.family_members("nymphalidae"), "genus_key")
        assert genera["nosuchgenus"]["col_id"] is None
        assert genera["nosuchgenus"]["image_count"] == 1

    def test_without_the_backbone_the_rollup_still_returns_genera(
        self, repository_without_backbone
    ):
        genera = by_key(
            repository_without_backbone.family_members("nymphalidae"), "genus_key"
        )
        assert "coenonympha" in genera
        assert genera["coenonympha"]["image_count"] == 5
        # Placement is all that is lost.
        assert genera["coenonympha"]["subfamily"] is None

    def test_lists_a_col_genus_the_collection_holds_nothing_of(self, repository):
        """The tree is the classification; a gap in the collection shows."""
        genera = by_key(repository.family_members("erebidae"), "genus_key")
        assert set(genera) == {"zzzonympha"}
        assert genera["zzzonympha"]["col_id"] == "GEN3"
        assert genera["zzzonympha"]["image_count"] == 0
        assert genera["zzzonympha"]["species_count"] == 0

    def test_an_unknown_family_has_no_members(self, repository):
        assert repository.family_members("nosuchfamily") == []


class TestOrderMembers:
    def test_lists_every_col_family_including_those_without_images(self, repository):
        """The tree is the backbone's classification, not the collection's."""
        rows = by_key(repository.order_members("lepidoptera"), "family_key")
        assert set(rows) == {"nymphalidae", "erebidae", "hesperiidae"}
        assert rows["erebidae"]["image_count"] == 0
        assert rows["hesperiidae"]["species_count"] == 0

    def test_rolls_the_collection_up_to_each_family(self, repository):
        nymphalidae = by_key(repository.order_members("lepidoptera"), "family_key")[
            "nymphalidae"
        ]
        # Every image matched to a species; genus-only records count nowhere.
        assert nymphalidae["image_count"] == 9
        assert nymphalidae["genus_count"] == 4
        assert nymphalidae["species_count"] == 5

    def test_carries_the_col_placement(self, repository):
        rows = by_key(repository.order_members("lepidoptera"), "family_key")
        assert rows["erebidae"]["suborder"] == "Glossata"
        assert rows["erebidae"]["superfamily"] == "Noctuoidea"
        assert rows["nymphalidae"]["family_name"] == "Nymphalidae"
        assert rows["nymphalidae"]["authorship"] == "Rafinesque, 1815"

    def test_another_order_has_no_members(self, repository):
        assert repository.order_members("coleoptera") == []

    def test_without_the_backbone_there_is_no_order(self, repository_without_backbone):
        assert repository_without_backbone.order_members("lepidoptera") == []
        assert (
            repository_without_backbone.representative_images(
                "order", "lepidoptera", 20
            )
            == []
        )


class TestFamilyImages:
    def test_one_image_per_family_with_records(self, repository):
        rows = repository.family_images("lepidoptera")
        # Erebidae and Hesperiidae have nothing photographed.
        assert [row["family_key"] for row in rows] == ["nymphalidae"]

    def test_shows_the_most_photographed_species_dorsally(self, repository):
        (row,) = repository.family_images("lepidoptera")
        # Four images of C. pamphilus, counting its subspecies; i1 and i10 are
        # its dorsal views, and the lower id wins.
        assert row["display_name"] == "Coenonympha pamphilus"
        assert row["img_id"] == "i1"

    def test_without_the_backbone_there_are_none(self, repository_without_backbone):
        assert repository_without_backbone.family_images("lepidoptera") == []


class TestColTotals:
    """The denominators for the header's coverage figures."""

    def test_counts_every_accepted_taxon_in_an_order(self, repository):
        totals = repository.col_totals("order", "lepidoptera")
        assert totals["family_total"] == 3
        # Zzzonympha is a homonym in two families; it is one genus name.
        assert totals["genus_total"] == 3
        assert totals["species_total"] == 6

    def test_counts_the_genera_and_species_of_a_family(self, repository):
        totals = repository.col_totals("family", "nymphalidae")
        assert totals["genus_total"] == 3
        assert totals["species_total"] == 6

    def test_counts_species_not_synonyms_or_subspecies(self, repository):
        # Papilio pamphilus is a synonym and Coenonympha incertae is unranked.
        assert repository.col_totals("genus", "coenonympha")["species_total"] == 3

    def test_without_the_backbone_there_is_no_total(self, repository_without_backbone):
        assert repository_without_backbone.col_totals("family", "nymphalidae") is None


class TestGenusMembers:
    def test_lists_species_with_their_image_counts(self, repository):
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        # Three images of the species plus one of its subspecies, which is
        # folded in rather than standing beside it under the same name.
        assert species["coenonympha_pamphilus"]["image_count"] == 4
        assert "coenonympha_pamphilus_lyllus" not in species

    def test_lists_a_col_species_the_collection_holds_nothing_of(self, repository):
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        row = species["coenonympha_dubia"]
        assert row["image_count"] == 0
        assert row["species_name"] == "Coenonympha dubia"
        assert row["recorded_name"] is None

    def test_a_held_species_is_not_listed_twice(self, repository):
        """Coenonympha tullia is held under a renamed record key."""
        names = [row["species_name"] for row in repository.genus_members("coenonympha")]
        assert names.count("Coenonympha tullia") == 1
        assert names.count("Coenonympha pamphilus") == 1

    def test_keys_a_renamed_species_on_the_name_the_collection_records(
        self, repository
    ):
        """The href has to resolve, so the key stays the recorded one.

        A species page looks its images up by `image_meta.species`. Keying this
        node on the accepted name would give a page that renders a header over
        an empty gallery.
        """
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        row = species["oldgenus_renamed"]
        assert row["species_name"] == "Coenonympha tullia"
        assert row["recorded_name"] == "Oldgenus renamed"

    def test_links_the_binomial_even_when_a_subspecies_is_commoner(
        self, repository
    ):
        """The route is a binomial and matches the recorded string exactly.

        Linking a trinomial would be cut to its binomial on the way into the
        URL and open a gallery holding none of its images.
        """
        client = repository.db_client
        client.execute(
            "INSERT INTO image_meta (img_id, species, family, class_dv) "
            "SELECT 'ssp' || i, 'coenonympha_pamphilus_lyllus', 'nymphalidae', "
            "'dorsal' FROM range(5) t(i)"
        )
        client.execute(
            "INSERT INTO image_meta_taxonomy (img_id, update_status, "
            "accepted_name, accepted_species_name, display_accepted_name, "
            "accepted_family) SELECT 'ssp' || i, 'MATCHED', "
            "'Coenonympha pamphilus', 'Coenonympha pamphilus', "
            "'Coenonympha pamphilus', 'Nymphalidae' FROM range(5) t(i)"
        )
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        assert species["coenonympha_pamphilus"]["image_count"] == 9
        assert "coenonympha_pamphilus_lyllus" not in species

    def test_a_genus_only_record_is_not_a_species(self, repository):
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        assert "coenonympha" not in species

    def test_resolves_authorship_through_the_backbone(self, repository):
        species = by_key(repository.genus_members("coenonympha"), "species_key")
        assert species["coenonympha_pamphilus"]["authorship"] == "(Linnaeus, 1758)"
        assert species["coenonympha_pamphilus"]["col_id"] == "AAA1"

    def test_without_the_backbone_species_keep_their_recorded_names(
        self, repository_without_backbone
    ):
        species = by_key(
            repository_without_backbone.genus_members("coenonympha"), "species_key"
        )
        assert species["coenonympha_pamphilus"]["authorship"] is None
        assert species["coenonympha_pamphilus"]["species_name"] == (
            "Coenonympha pamphilus"
        )


class TestRepresentativeImages:
    def test_draws_one_image_per_species_when_species_are_plentiful(self, repository):
        rows = repository.representative_images("family", "nymphalidae", 4)
        assert len(rows) == 4
        assert len({row["species"] for row in rows}) == 4

    def test_never_shows_one_species_twice(self, repository):
        """The strip sits under a heading naming these as the species present.

        Coenonympha has two of them, so a grid asked for four still shows two:
        padding it with a second specimen of the best-photographed one would
        put the same name in the grid twice.
        """
        rows = repository.representative_images("genus", "coenonympha", 4)
        assert len(rows) == 2
        assert len({row["species"] for row in rows}) == 2

    def test_a_one_species_genus_shows_one_tile(self, repository):
        rows = repository.representative_images("genus", "zzzonympha", 20)
        assert len(rows) == 1

    def test_prefers_a_dorsal_view_within_a_species(self, repository):
        rows = repository.representative_images("genus", "coenonympha", 1)
        # i1 is the only dorsal image of coenonympha_pamphilus.
        assert rows[0]["img_id"] == "i1"

    def test_excludes_records_identified_only_to_genus(self, repository):
        """Every tile links to a species page, so every tile needs a species."""
        rows = repository.representative_images("family", "nymphalidae", 20)
        assert "coenonympha" not in {row["species"] for row in rows}

    def test_excludes_unmatched_images(self, repository):
        rows = repository.representative_images("family", "nymphalidae", 20)
        assert "unresolvable_name" not in {row["species"] for row in rows}

    def test_a_subspecies_does_not_take_a_tile_of_its_own(self, repository):
        """`coenonympha_pamphilus_lyllus` is the same species to a reader.

        Both records link to the same page, so spreading across the raw
        recorded keys would put two identical tiles in the grid.
        """
        rows = repository.representative_images("genus", "coenonympha", 20)
        binomials = [row["species"] for row in rows]
        assert binomials.count("coenonympha_pamphilus") == 1
        assert "coenonympha_pamphilus_lyllus" not in binomials

    def test_is_deterministic_across_calls(self, repository):
        """These responses are cached for thirty days behind one ETag."""
        first = repository.representative_images("family", "nymphalidae", 5)
        second = repository.representative_images("family", "nymphalidae", 5)
        assert [row["img_id"] for row in first] == [row["img_id"] for row in second]

    def test_an_order_draws_from_every_family_in_it(self, repository):
        rows = repository.representative_images("order", "lepidoptera", 20)
        # One tile per species across the order's families.
        assert len(rows) == 5
        assert len({row["display_name"] for row in rows}) == 5


class TestAvailability:
    def test_membership_is_unavailable_without_the_harmonized_taxonomy(
        self, memory_duckdb
    ):
        """Strict membership is defined in terms of that table.

        Falling back to the recorded taxonomy would answer a different
        question than the counts on the page claim to answer, so the page is
        not served at all.
        """
        repository = _repository(memory_duckdb)
        assert repository.harmonized_available() is False
        assert repository.family_members("nymphalidae") == []
        assert repository.representative_images("family", "nymphalidae", 20) == []


def _family_row(genus, **overrides):
    row = {
        "genus_key": genus,
        "genus_name": genus.capitalize(),
        "authorship": None,
        "col_id": f"ID-{genus}",
        "col_link": None,
        "col_family": "nymphalidae",
        "subfamily": None,
        "tribe": None,
        "subtribe": None,
        "species_count": 1,
        "image_count": 1,
    }
    row.update(overrides)
    return row


def find(nodes: list[TaxonNode], name: str) -> TaxonNode | None:
    for node in nodes:
        if node.name == name:
            return node
        found = find(node.children, name)
        if found is not None:
            return found
    return None


def require_node(nodes: list[TaxonNode], name: str) -> TaxonNode:
    """Find a node the test expects the tree to hold."""
    found = find(nodes, name)
    assert found is not None, name
    return found


class TestTreeAssembly:
    def test_nests_genus_under_tribe_under_subfamily(self):
        tree = build_tree(
            [_family_row("aphantopus", subfamily="Satyrinae", tribe="Coenonymphini")],
            scope="family",
            scope_key="nymphalidae",
        )
        subfamily = tree[0]
        assert subfamily.rank == "subfamily"
        assert subfamily.children[0].rank == "tribe"
        assert subfamily.children[0].children[0].rank == "genus"

    def test_omits_a_rank_col_has_not_populated(self):
        """A missing tribe is skipped, not rendered as a nameless level."""
        tree = build_tree(
            [_family_row("coenonympha", subfamily="Satyrinae")],
            scope="family",
            scope_key="nymphalidae",
        )
        assert [node.rank for node in tree] == ["subfamily"]
        assert tree[0].children[0].rank == "genus"

    def test_counts_roll_up_to_every_ancestor(self):
        tree = build_tree(
            [
                _family_row(
                    "a", subfamily="Satyrinae", species_count=3, image_count=10
                ),
                _family_row("b", subfamily="Satyrinae", species_count=2, image_count=5),
            ],
            scope="family",
            scope_key="nymphalidae",
        )
        subfamily = tree[0]
        assert subfamily.species_count == 5
        assert subfamily.image_count == 15
        assert subfamily.genus_count == 2

    def test_genera_are_alphabetical_within_their_rank(self):
        """A classification is looked up, not scanned.

        The rows arrive most-photographed first, which is what picks the
        image strip and is no help at all to someone hunting for a genus.
        """
        tree = build_tree(
            [
                _family_row("zephyrus", subfamily="Satyrinae", image_count=99),
                _family_row("aphantopus", subfamily="Satyrinae", image_count=2),
                _family_row("melanargia", subfamily="Satyrinae", image_count=50),
            ],
            scope="family",
            scope_key="nymphalidae",
        )
        assert [node.name for node in tree[0].children] == [
            "Aphantopus",
            "Melanargia",
            "Zephyrus",
        ]

    def test_grouping_ranks_sort_before_the_genera_beside_them(self):
        """A tribe sorted in among loose genera reads as a list that has lost
        its structure, so the levels stay apart and each is alphabetical."""
        tree = build_tree(
            [
                _family_row("zephyrus"),
                _family_row("aphantopus"),
                _family_row("melitaea", subfamily="Nymphalinae"),
            ],
            scope="family",
            scope_key="nymphalidae",
        )
        assert [node.rank for node in tree] == ["subfamily", "genus", "genus"]
        assert [node.name for node in tree] == [
            "Nymphalinae",
            "Aphantopus",
            "Zephyrus",
        ]

    def test_species_are_alphabetical_within_a_subgenus(self):
        def species(key, name, subgenus=None, images=1):
            return {
                "species_key": key,
                "species_name": name,
                "recorded_name": name,
                "authorship": None,
                "col_id": None,
                "col_link": None,
                "col_status": None,
                "subgenus": subgenus,
                "image_count": images,
            }

        tree = build_tree(
            [
                species("danaus_plexippus", "Danaus plexippus", "Danaus", 900),
                species("danaus_cleophile", "Danaus cleophile", "Danaus", 3),
                species("danaus_erippus", "Danaus erippus", "Danaus", 40),
            ],
            scope="genus",
            scope_key="danaus",
        )
        assert [node.name for node in tree[0].children] == [
            "Danaus cleophile",
            "Danaus erippus",
            "Danaus plexippus",
        ]

    def test_a_genus_col_cannot_place_goes_in_the_unplaced_bucket(self):
        tree = build_tree(
            [_family_row("ghost", col_id=None, col_family=None)],
            scope="family",
            scope_key="nymphalidae",
        )
        assert tree[-1].key == UNPLACED_KEY
        assert tree[-1].placed is False
        assert tree[-1].children[0].placed is False

    def test_a_genus_col_places_in_another_family_is_unplaced(self):
        """Better to admit we cannot place it than to file it under a
        subfamily belonging to a different family."""
        tree = build_tree(
            [_family_row("stray", col_family="erebidae", subfamily="Arctiinae")],
            scope="family",
            scope_key="nymphalidae",
        )
        assert find(tree, "Arctiinae") is None
        assert tree[-1].key == UNPLACED_KEY

    def test_the_unplaced_bucket_comes_last(self):
        tree = build_tree(
            [
                _family_row("ghost", col_id=None),
                _family_row("real", subfamily="Satyrinae"),
            ],
            scope="family",
            scope_key="nymphalidae",
        )
        assert tree[-1].key == UNPLACED_KEY

    def test_a_genus_leaf_links_to_its_page(self):
        tree = build_tree(
            [_family_row("aphantopus")], scope="family", scope_key="nymphalidae"
        )
        assert tree[0].href == "/genus/aphantopus"

    def test_grouping_ranks_never_link(self):
        """Only ranks with a page of their own are links, which is also what
        keeps a link out of every `<summary>` on the rendered page."""
        tree = build_tree(
            [_family_row("aphantopus", subfamily="Satyrinae", tribe="Coenonymphini")],
            scope="family",
            scope_key="nymphalidae",
        )
        assert tree[0].href is None
        assert tree[0].children[0].href is None

    def test_a_subgenus_is_reduced_to_its_parenthetical(self):
        """Catalogue of Life writes `Genus (Subgenus)`; only the second half
        names the subgenus, and the genus already has its own node."""
        tree = build_tree(
            [
                {
                    "species_key": "danaus_genutia",
                    "species_name": "Danaus genutia",
                    "recorded_name": "Danaus genutia",
                    "authorship": None,
                    "col_id": "X1",
                    "col_link": None,
                    "col_status": "accepted",
                    "subgenus": "Danaus (Salatura)",
                    "image_count": 2,
                }
            ],
            scope="genus",
            scope_key="danaus",
        )
        assert tree[0].name == "Salatura"
        assert tree[0].rank == "subgenus"

    def test_a_species_leaf_links_on_its_recorded_key(self):
        tree = build_tree(
            [
                {
                    "species_key": "oldgenus_renamed",
                    "species_name": "Coenonympha tullia",
                    "recorded_name": "Oldgenus renamed",
                    "authorship": None,
                    "col_id": None,
                    "col_link": None,
                    "col_status": None,
                    "subgenus": None,
                    "image_count": 1,
                }
            ],
            scope="genus",
            scope_key="coenonympha",
        )
        assert tree[0].href == "/species/oldgenus_renamed"
        assert tree[0].key == "oldgenus_renamed"
        assert tree[0].name == "Coenonympha tullia"
        assert tree[0].recorded_name == "Oldgenus renamed"

    def test_a_recorded_trinomial_links_to_the_binomial_route(self):
        """The species route parses two parts, which is what the rest of the
        site links by; the key stays the full recorded name."""
        tree = build_tree(
            [
                {
                    "species_key": "danaus_eresimus_tethys",
                    "species_name": "Danaus eresimus tethys",
                    "recorded_name": "Danaus eresimus tethys",
                    "authorship": None,
                    "col_id": None,
                    "col_link": None,
                    "col_status": None,
                    "subgenus": None,
                    "image_count": 4,
                }
            ],
            scope="genus",
            scope_key="danaus",
        )
        assert tree[0].href == "/species/danaus_eresimus"
        assert tree[0].key == "danaus_eresimus_tethys"

    def test_a_subgenus_parenthetical_is_not_a_rename(self):
        """`Danaus (Salatura) genutia` is the name the collection recorded.

        Without comparing canonically, every species in a genus that has
        subgenera would claim to have been renamed.
        """
        tree = build_tree(
            [
                {
                    "species_key": "danaus_genutia",
                    "species_name": "Danaus (Salatura) genutia",
                    "recorded_name": "Danaus genutia",
                    "authorship": None,
                    "col_id": None,
                    "col_link": None,
                    "col_status": None,
                    "subgenus": None,
                    "image_count": 2,
                }
            ],
            scope="genus",
            scope_key="danaus",
        )
        assert tree[0].recorded_name is None

    def test_a_species_that_was_not_renamed_says_nothing_about_it(self):
        tree = build_tree(
            [
                {
                    "species_key": "coenonympha_pamphilus",
                    "species_name": "Coenonympha pamphilus",
                    "recorded_name": "Coenonympha pamphilus",
                    "authorship": None,
                    "col_id": None,
                    "col_link": None,
                    "col_status": None,
                    "subgenus": None,
                    "image_count": 1,
                }
            ],
            scope="genus",
            scope_key="coenonympha",
        )
        assert tree[0].recorded_name is None


def _order_row(family, **overrides):
    row = {
        "family_key": family,
        "family_name": family.capitalize(),
        "authorship": None,
        "col_id": f"ID-{family}",
        "col_link": None,
        "suborder": None,
        "superfamily": None,
        "genus_count": 1,
        "species_count": 1,
        "image_count": 1,
    }
    row.update(overrides)
    return row


class TestOrderTree:
    def build(self, rows):
        return build_order_tree(rows, order_key="lepidoptera", order_name="Lepidoptera")

    def test_the_order_is_the_single_root(self):
        tree = self.build([_order_row("nymphalidae", superfamily="Papilionoidea")])
        assert len(tree) == 1
        assert tree[0].rank == "order"
        assert tree[0].name == "Lepidoptera"
        assert tree[0].href is None

    def test_nests_family_under_superfamily_under_suborder(self):
        tree = self.build(
            [_order_row("erebidae", suborder="Glossata", superfamily="Noctuoidea")]
        )
        suborder = tree[0].children[0]
        assert (suborder.rank, suborder.name) == ("suborder", "Glossata")
        superfamily = suborder.children[0]
        assert (superfamily.rank, superfamily.name) == ("superfamily", "Noctuoidea")
        assert superfamily.children[0].rank == "family"

    def test_a_family_with_images_links_to_its_page(self):
        tree = self.build([_order_row("nymphalidae")])
        assert require_node(tree, "Nymphalidae").href == "/family/nymphalidae"

    def test_a_family_without_images_does_not_link(self):
        """Its family page would answer 404."""
        tree = self.build(
            [_order_row("erebidae", genus_count=0, species_count=0, image_count=0)]
        )
        family = require_node(tree, "Erebidae")
        assert family.href is None
        assert family.genus_count is None

    def test_counts_roll_up_to_the_root(self):
        tree = self.build(
            [
                _order_row(
                    "nymphalidae",
                    superfamily="Papilionoidea",
                    genus_count=4,
                    species_count=5,
                    image_count=10,
                ),
                _order_row(
                    "hesperiidae",
                    superfamily="Papilionoidea",
                    genus_count=2,
                    species_count=3,
                    image_count=6,
                ),
                _order_row(
                    "erebidae",
                    superfamily="Noctuoidea",
                    genus_count=0,
                    species_count=0,
                    image_count=0,
                ),
            ]
        )
        root = tree[0]
        # Only families the collection has images of count as its families.
        assert root.family_count == 2
        assert root.genus_count == 6
        assert root.species_count == 8
        assert root.image_count == 16
        assert require_node(tree, "Noctuoidea").family_count is None
        assert require_node(tree, "Papilionoidea").family_count == 2

    def test_grouping_ranks_sort_before_the_families_beside_them(self):
        tree = self.build(
            [
                _order_row("aaafamily"),
                _order_row("zzzfamily", superfamily="Papilionoidea"),
            ]
        )
        assert [child.name for child in tree[0].children] == [
            "Papilionoidea",
            "Aaafamily",
        ]


class TestOrderOverview:
    @pytest.fixture
    def overview(self, repository, monkeypatch):
        PAYLOAD_CACHE.clear()
        monkeypatch.setattr(
            higher_taxa_query, "HigherTaxonRepository", lambda _db: repository
        )
        monkeypatch.setattr(
            OrderOverview, "_classification", AsyncMock(return_value=None)
        )
        request = cast(
            Request,
            SimpleNamespace(
                app=SimpleNamespace(state=SimpleNamespace(duck_db=repository.db_client))
            ),
        )
        yield OrderOverview(request=request, name="Lepidoptera")
        PAYLOAD_CACHE.clear()

    @pytest.mark.asyncio
    async def test_the_payload_counts_only_families_with_images(self, overview):
        payload = await overview.overview()
        assert payload["rank"] == "order"
        assert payload["counts"]["familyCount"] == 1
        assert payload["counts"]["imageCount"] == 9
        assert payload["tree"][0]["rank"] == "order"
        assert payload["tree"][0]["familyCount"] == 1

    @pytest.mark.asyncio
    async def test_the_counts_carry_col_totals_for_coverage(self, overview):
        counts = (await overview.overview())["counts"]
        assert counts["familyTotal"] == 3
        assert counts["genusTotal"] == 3
        assert counts["speciesTotal"] == 6

    @pytest.mark.asyncio
    async def test_a_second_request_is_served_from_the_memo(
        self, overview, repository, monkeypatch
    ):
        """The order scans the whole collection; it should do so once."""
        first = await overview.overview()
        calls = []
        monkeypatch.setattr(
            repository, "order_members", lambda key: calls.append(key) or []
        )
        second = await overview.overview()
        assert second == first
        assert calls == []

    @pytest.mark.asyncio
    async def test_an_order_with_no_images_is_not_found(
        self, overview, repository, monkeypatch
    ):
        monkeypatch.setattr(
            repository,
            "order_members",
            lambda key: [_order_row("erebidae", image_count=0)],
        )
        assert await overview.overview() is None


class TestTotalsAttachment:
    def test_a_total_is_set_only_beside_a_count_of_its_rank(self):
        """A genus page has no genus count, so it gets no genus total."""
        counts = HigherTaxonOverview._with_totals(
            HigherTaxonCounts(species_count=2, image_count=5),
            {"family_total": 0, "genus_total": 1, "species_total": 4},
        )
        assert counts.family_total is None
        assert counts.genus_total is None
        assert counts.species_total == 4

    def test_a_zero_total_is_left_unset(self):
        """CoL knowing nothing is not 0% coverage."""
        counts = HigherTaxonOverview._with_totals(
            HigherTaxonCounts(genus_count=1, species_count=1, image_count=1),
            {"family_total": 0, "genus_total": 0, "species_total": 0},
        )
        assert counts.genus_total is None
        assert counts.species_total is None

    def test_without_totals_the_counts_are_unchanged(self):
        counts = HigherTaxonCounts(genus_count=1, species_count=1, image_count=1)
        assert HigherTaxonOverview._with_totals(counts, None) == counts


class TestTaxaWithoutRecords:
    def test_a_genus_without_images_does_not_link_or_count(self):
        tree = build_rooted_tree(
            [
                _family_row("aphantopus", subfamily="Satyrinae"),
                _family_row(
                    "ghostus", subfamily="Satyrinae", species_count=0, image_count=0
                ),
            ],
            scope="family",
            key="nymphalidae",
            name="Nymphalidae",
        )
        assert require_node(tree, "Ghostus").href is None
        assert require_node(tree, "Aphantopus").href == "/genus/aphantopus"
        assert require_node(tree, "Satyrinae").genus_count == 1

    def test_a_species_without_images_does_not_link_or_count(self):
        rows = [
            {
                "species_key": "danaus_plexippus",
                "species_name": "Danaus plexippus",
                "recorded_name": "Danaus plexippus",
                "image_count": 3,
            },
            {
                "species_key": "danaus_ghost",
                "species_name": "Danaus ghost",
                "recorded_name": None,
                "image_count": 0,
            },
        ]
        tree = build_rooted_tree(rows, scope="genus", key="danaus", name="Danaus")
        assert require_node(tree, "Danaus ghost").href is None
        assert require_node(tree, "Danaus ghost").species_count == 0
        assert tree[0].species_count == 1

    @pytest.mark.parametrize("scope", ["family", "genus"])
    def test_every_rank_roots_its_tree_on_the_taxon(self, scope):
        tree = build_rooted_tree([], scope=scope, key="x", name="X")
        assert [(node.rank, node.name) for node in tree] == [(scope, "X")]

    def test_the_unplaced_bucket_stays_last_under_the_root(self):
        tree = build_rooted_tree(
            [
                _family_row("zeta", subfamily="Satyrinae"),
                _family_row("alpha", col_id=None),
            ],
            scope="family",
            key="nymphalidae",
            name="Nymphalidae",
        )
        assert tree[0].children[-1].key == UNPLACED_KEY

    def test_header_counts_only_taxa_with_images(self):
        overview = HigherTaxonOverview.__new__(HigherTaxonOverview)
        overview.rank = "family"
        counts = overview._counts(
            [
                _family_row("aphantopus", species_count=2, image_count=4),
                _family_row("ghostus", species_count=0, image_count=0),
            ]
        )
        assert (counts.genus_count, counts.species_count, counts.image_count) == (
            1,
            2,
            4,
        )


def test_family_images_attach_to_family_nodes_only():
    tree = build_order_tree(
        [_order_row("nymphalidae", superfamily="Papilionoidea")],
        order_key="lepidoptera",
        order_name="Lepidoptera",
    )
    attach_family_images(
        tree,
        [
            {"family_key": "nymphalidae", "img_id": "i1", "display_name": "X y"},
            # A key shared with a non-family node must not leak onto it.
            {"family_key": "papilionoidea", "img_id": "i2", "display_name": "Z"},
        ],
    )
    family = require_node(tree, "Nymphalidae")
    assert (family.img_id, family.img_name) == ("i1", "X y")
    assert require_node(tree, "Papilionoidea").img_id is None
    assert tree[0].img_id is None
