"""Tests for resolving names against the local CoL backbone.

The behaviour that matters is synonym resolution: GbifTaxonSearch took the
first result of a `limit=1` API call without checking its status, so a synonym
was presented as though it were the accepted name.
"""

import asyncio
import os

import pytest

from app.services.col import ColBackboneService, ColTaxonSearch


@pytest.fixture
def backbone(memory_duckdb, col_fixture_dir):
    service = ColBackboneService.__new__(ColBackboneService)
    service.db_client = memory_duckdb
    service.path = os.path.join(col_fixture_dir, "NameUsage.tsv")
    service.vernacular_path = os.path.join(col_fixture_dir, "VernacularName.tsv")
    service.table = "col_taxonomy"
    service.vernacular_table = "col_vernacular"
    service.clade_rank = "order"
    service.clade_value = "Lepidoptera"
    service.skip_ingestion = False
    service._ingest_name_usage()
    service._ingest_vernacular_names()

    search = ColTaxonSearch.__new__(ColTaxonSearch)
    search.db_client = memory_duckdb
    search.table = "col_taxonomy"
    search.vernacular_table = "col_vernacular"
    # Not created here: resolution must degrade to the two exact passes when
    # no harmonization run has been loaded.
    search.matches_table = "col_taxonomy_matches"
    return search


def resolve(search, name):
    return asyncio.run(search.search(name))


class TestAcceptedNames:
    def test_resolves_an_accepted_species(self, backbone):
        result = resolve(backbone, "Coenonympha pamphilus")
        assert result["scientificName"] == "Coenonympha pamphilus"
        assert result["taxonomicStatus"] == "accepted"
        assert result["colId"] == "AAA1"

    def test_returns_the_full_lineage(self, backbone):
        result = resolve(backbone, "Coenonympha pamphilus")
        assert result["kingdom"] == "Animalia"
        assert result["phylum"] == "Arthropoda"
        # Serialized under the `class` alias, which the frontend reads directly.
        assert result["class"] == "Insecta"
        assert result["order"] == "Lepidoptera"
        assert result["family"] == "Nymphalidae"
        assert result["genus"] == "Coenonympha"

    def test_includes_intermediate_ranks_gbif_never_supplied(self, backbone):
        result = resolve(backbone, "Coenonympha pamphilus")
        assert result["subphylum"] == "Hexapoda"
        assert result["superfamily"] == "Papilionoidea"
        assert result["subfamily"] == "Satyrinae"
        assert result["tribe"] == "Coenonymphini"

    def test_omits_ranks_col_does_not_populate(self, backbone):
        result = resolve(backbone, "Coenonympha pamphilus")
        # None rather than "Unknown": the UI drops the row entirely.
        assert result["subclass"] is None
        assert result["subgenus"] is None

    def test_carries_the_vernacular_name(self, backbone):
        assert resolve(backbone, "Coenonympha pamphilus")["vernacularName"] == (
            "Small heath"
        )

    def test_no_input_name_when_the_query_is_already_accepted(self, backbone):
        assert resolve(backbone, "Coenonympha pamphilus")["inputName"] is None


class TestSynonymResolution:
    def test_synonym_resolves_to_the_accepted_taxon(self, backbone):
        result = resolve(backbone, "Papilio pamphilus")
        assert result["scientificName"] == "Coenonympha pamphilus"
        assert result["colId"] == "AAA1"

    def test_synonym_keeps_the_queried_name(self, backbone):
        # The species page shows "Recorded as" so the reader can see why the
        # name they searched for is not the name being displayed.
        assert resolve(backbone, "Papilio pamphilus")["inputName"] == (
            "Papilio pamphilus"
        )

    def test_synonym_inherits_the_accepted_lineage(self, backbone):
        # The synonym row itself carries no lineage at all.
        result = resolve(backbone, "Papilio pamphilus")
        assert result["family"] == "Nymphalidae"
        assert result["order"] == "Lepidoptera"


class TestQueryNormalization:
    @pytest.mark.parametrize(
        "query",
        [
            "coenonympha_pamphilus",  # the occurrence-table slug
            "Coenonympha pamphilus",
            "  COENONYMPHA   PAMPHILUS  ",
        ],
    )
    def test_equivalent_spellings_resolve_alike(self, backbone, query):
        assert resolve(backbone, query)["colId"] == "AAA1"

    @pytest.mark.parametrize("query", ["", "   ", None])
    def test_empty_queries_return_none(self, backbone, query):
        assert resolve(backbone, query) is None

    def test_unknown_name_returns_none(self, backbone):
        assert resolve(backbone, "Nonexistent taxon") is None


class TestRankScopedSearch:
    def test_genus_lookup_names_itself(self, backbone):
        result = asyncio.run(backbone.search_at_rank("Coenonympha", "genus"))
        # CoL leaves a usage's own rank out of its lineage columns, so this
        # only works because from_row backfills it.
        assert result["genus"] == "Coenonympha"
        assert result["family"] == "Nymphalidae"

    def test_genus_lookup_rejects_a_species_name(self, backbone):
        assert (
            asyncio.run(backbone.search_at_rank("Coenonympha pamphilus", "genus"))
            is None
        )

    def test_species_is_blank_for_a_genus_usage(self, backbone):
        assert (
            asyncio.run(backbone.search_at_rank("Coenonympha", "genus"))["species"]
            == ""
        )


class TestSubgenusNotation:
    """CoL writes zoological names with the subgenus in parentheses."""

    def test_binomial_finds_a_name_recorded_with_a_subgenus(self, backbone):
        # The fixture holds 'Zzzonympha (Sub) tricolor'; the collection would
        # only ever write 'zzzonympha_tricolor'.
        result = resolve(backbone, "zzzonympha_tricolor")
        assert result is not None
        assert result["colId"] == "SUBG1"

    def test_the_full_written_form_also_resolves(self, backbone):
        result = resolve(backbone, "Zzzonympha (Sub) tricolor")
        assert result is not None
        assert result["colId"] == "SUBG1"


class TestHarmonizationFallback:
    def test_missing_matches_table_is_not_an_error(self, backbone):
        # Before the first colharmonize run, the fallback query fails against
        # a table that does not exist; the caller must simply see no match.
        assert resolve(backbone, "Nonexistent taxon") is None

    def test_a_loaded_run_resolves_a_name_col_does_not_have(
        self, backbone, memory_duckdb
    ):
        memory_duckdb.execute(
            """
            CREATE TABLE col_taxonomy_matches (
                normalized_name VARCHAR, accepted_id VARCHAR, match_score INTEGER
            )
            """
        )
        # A genus reassignment: CoL has no usage under the recorded name, but
        # the run matched it by family and epithet.
        memory_duckdb.execute_prepared(
            "INSERT INTO col_taxonomy_matches VALUES (?, ?, ?)",
            ["oldgenus pamphilus", "AAA1", 4300],
        )
        result = resolve(backbone, "oldgenus_pamphilus")
        assert result is not None
        assert result["scientificName"] == "Coenonympha pamphilus"


class TestMissingBackbone:
    """Before the CoL release has been ingested, or without one on disk.

    This is the state a fresh checkout starts in, and the one that took every
    species page down: the lookups ran anyway and DuckDB raised a catalog
    error three times per page view.
    """

    @pytest.fixture
    def searcher(self, memory_duckdb):
        search = ColTaxonSearch.__new__(ColTaxonSearch)
        search.db_client = memory_duckdb
        search.table = "col_taxonomy"
        search.vernacular_table = "col_vernacular"
        search.matches_table = "col_taxonomy_matches"
        return search

    def test_search_returns_none_instead_of_raising(self, searcher):
        assert resolve(searcher, "Coenonympha pamphilus") is None

    def test_rank_scoped_search_returns_none(self, searcher):
        assert asyncio.run(searcher.search_at_rank("Nymphalidae", "family")) is None

    def test_the_backbone_is_probed_once_per_instance(self, searcher, monkeypatch):
        probes = []
        original = searcher.db_client.table_exists

        def counting_probe(name):
            probes.append(name)
            return original(name)

        monkeypatch.setattr(searcher.db_client, "table_exists", counting_probe)
        # search() makes three lookups: name_norm, canonical_key, then the
        # harmonization fallback. All three must share one probe.
        resolve(searcher, "Coenonympha pamphilus")
        assert probes == ["col_taxonomy"]

    def test_a_backbone_that_appears_later_is_used(
        self, memory_duckdb, col_fixture_dir
    ):
        searcher = ColTaxonSearch.__new__(ColTaxonSearch)
        searcher.db_client = memory_duckdb
        searcher.table = "col_taxonomy"
        searcher.vernacular_table = "col_vernacular"
        searcher.matches_table = "col_taxonomy_matches"
        assert resolve(searcher, "Coenonympha pamphilus") is None

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

        # A new request builds a new searcher, so the cache does not go stale.
        fresh = ColTaxonSearch.__new__(ColTaxonSearch)
        fresh.db_client = memory_duckdb
        fresh.table = "col_taxonomy"
        fresh.vernacular_table = "col_vernacular"
        fresh.matches_table = "col_taxonomy_matches"
        assert resolve(fresh, "Coenonympha pamphilus")["colId"] == "AAA1"
