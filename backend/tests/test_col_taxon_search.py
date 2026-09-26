"""Tests for resolving names against the local CoL backbone.

The behaviour that matters is synonym resolution: GbifTaxonSearch took the
first result of a `limit=1` API call without checking its status, so a synonym
was presented as though it were the accepted name.
"""

import asyncio
import os

import pytest

from app.database.model import ColReference, ColTaxonomy, ColTypeSpecimen
from app.services.col import ColBackboneService, ColTaxonSearch


@pytest.fixture
def backbone(memory_duckdb, col_fixture_dir):
    service = ColBackboneService.__new__(ColBackboneService)
    service.db_client = memory_duckdb
    service.path = os.path.join(col_fixture_dir, "NameUsage.tsv")
    service.vernacular_path = os.path.join(col_fixture_dir, "VernacularName.tsv")
    service.table = "col_taxonomy"
    service.vernacular_table = "col_vernacular"
    service.type_material_path = os.path.join(col_fixture_dir, "TypeMaterial.tsv")
    service.type_material_table = "col_type_material"
    service.reference_path = os.path.join(col_fixture_dir, "Reference.tsv")
    service.reference_table = "col_reference"
    service.clade_rank = "order"
    service.clade_value = "Lepidoptera"
    service.skip_ingestion = False
    service._ingest_name_usage()
    service._ingest_vernacular_names()
    service._ingest_type_material()
    service._ingest_references()

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

    def test_the_subgenus_row_drops_the_leading_genus(self):
        # CoL stores the subgenus lineage column as 'Genus (Subgenus)'. The
        # genus already has its own row, so only the parenthesised name
        # belongs here.
        taxonomy = ColTaxonomy.from_row(
            {"scientific_name": "Zzzonympha tricolor", "subgenus": "Zzzonympha (Sub)"}
        )
        assert taxonomy.subgenus == "Sub"

    def test_a_bare_subgenus_is_left_alone(self):
        taxonomy = ColTaxonomy.from_row(
            {"scientific_name": "Zzzonympha tricolor", "subgenus": "Sub"}
        )
        assert taxonomy.subgenus == "Sub"

    def test_the_species_name_carries_no_subgenus(self):
        """The subgenus belongs in its own row, not inside the species name.

        `Danaus (Danaus) plexippus` is the name Catalogue of Life stores, but
        it is not a name to show a reader next to a Subgenus row saying the
        same thing — and it does not line up against the binomial every route
        and every image query in this application keys on.
        """
        taxonomy = ColTaxonomy.from_row(
            {
                "scientific_name": "Zzzonympha (Sub) tricolor",
                "taxon_rank": "species",
                "subgenus": "Zzzonympha (Sub)",
            }
        )
        assert taxonomy.species == "Zzzonympha tricolor"
        assert taxonomy.acceptedName == "Zzzonympha tricolor"
        assert taxonomy.subgenus == "Sub"
        # The verbatim Catalogue of Life name is still carried, for anything
        # that needs the name exactly as published.
        assert taxonomy.scientificName == "Zzzonympha (Sub) tricolor"

    def test_a_subspecies_keeps_its_third_epithet(self):
        taxonomy = ColTaxonomy.from_row(
            {
                "scientific_name": "Zzzonympha (Sub) tricolor minor",
                "taxon_rank": "subspecies",
            }
        )
        assert taxonomy.species == "Zzzonympha tricolor minor"

    def test_a_subgenus_usage_keeps_its_own_parenthetical_name(self):
        """Only species names are cleaned. Above species rank the
        parenthetical is the usage's own name, not noise inside another."""
        taxonomy = ColTaxonomy.from_row(
            {"scientific_name": "Zzzonympha (Sub)", "taxon_rank": "subgenus"}
        )
        assert taxonomy.acceptedName == "Zzzonympha (Sub)"

    def test_a_subgenus_usage_names_itself_without_its_genus(self):
        # A lookup of the subgenus usage backfills its own rank from the
        # scientific name, which carries the same parenthesised form.
        taxonomy = ColTaxonomy.from_row(
            {"scientific_name": "Zzzonympha (Sub)", "taxon_rank": "subgenus"}
        )
        assert taxonomy.subgenus == "Sub"


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
        result = resolve(fresh, "Coenonympha pamphilus")
        assert result is not None
        assert result["colId"] == "AAA1"


def detail(search, name):
    return asyncio.run(search.taxonomy_detail(name))


class TestTaxonomyDetail:
    def test_none_for_a_name_that_does_not_resolve(self, backbone):
        assert detail(backbone, "Nonexistent species") is None

    def test_none_for_a_genus(self, backbone):
        assert detail(backbone, "Coenonympha") is None

    def test_carries_the_classification(self, backbone):
        result = detail(backbone, "Coenonympha pamphilus")
        assert result["classification"]["family"] == "Nymphalidae"
        # Nested models keep the `class` alias.
        assert result["classification"]["class"] == "Insecta"
        assert result["detailAvailable"] is True

    def test_usages_list_the_accepted_name_then_the_basionym(self, backbone):
        usages = detail(backbone, "Coenonympha pamphilus")["nameUsages"]
        assert [usage["name"] for usage in usages] == [
            "Coenonympha pamphilus",
            "Papilio pamphilus",
        ]
        assert usages[0]["isAccepted"] and not usages[0]["isBasionym"]
        assert usages[1]["isBasionym"] and not usages[1]["isAccepted"]

    def test_usage_carries_its_publication(self, backbone):
        basionym = detail(backbone, "Coenonympha pamphilus")["nameUsages"][1]
        assert basionym["publishedIn"]["citation"].startswith("Linnaeus, C.")
        assert basionym["publishedIn"]["year"] == 1758
        assert basionym["publishedInPage"] == "472"
        assert basionym["nameStatus"] == "established"

    def test_nomenclature_names_the_original_combination(self, backbone):
        nomenclature = detail(backbone, "Coenonympha pamphilus")["nomenclature"]
        assert nomenclature["originalCombination"] == "Papilio pamphilus"
        assert nomenclature["originalAuthorship"] == "Linnaeus, 1758"
        assert nomenclature["isOriginalCombination"] is False
        assert nomenclature["originalPublication"]["year"] == 1758
        assert nomenclature["year"] == 1758

    def test_types_are_found_through_the_basionym(self, backbone):
        types = detail(backbone, "Coenonympha pamphilus")["typeMaterial"]
        # The lectotype outranks the paralectotype whatever the file order.
        assert [t["status"] for t in types] == ["lectotype", "paralectotype"]
        lectotype = types[0]
        assert lectotype["typifiedName"] == "Papilio pamphilus"
        assert lectotype["institutionCode"] == "LSL"
        assert lectotype["latitude"] == 59.86
        assert lectotype["reference"]["year"] == 2001
        assert lectotype["referencePage"] == "88"

    def test_reference_citation_is_assembled_when_missing(self, backbone):
        usage = detail(backbone, "Zzzonympha pamphilus")["nameUsages"][0]
        reference = usage["publishedIn"]
        assert "A new Zzzonympha" in reference["citation"]
        assert reference["year"] == 1900
        assert reference["link"] == "https://doi.org/10.1234/zzz"

    def test_holotype_on_the_accepted_name(self, backbone):
        result = detail(backbone, "Zzzonympha pamphilus")
        [holotype] = result["typeMaterial"]
        assert holotype["status"] == "holotype"
        # An unparseable coordinate is dropped, not a 500.
        assert holotype["latitude"] is None
        assert result["nomenclature"]["isOriginalCombination"] is True

    def test_no_types_recorded(self, backbone):
        result = detail(backbone, "Aphantopus hyperantus")
        assert result["typeMaterial"] == []
        # Recombined, but CoL links no basionym.
        assert result["nomenclature"]["isOriginalCombination"] is None

    def test_type_summary_comes_from_the_basionym(self, backbone):
        summary = detail(backbone, "Coenonympha pamphilus")["typeSummary"]
        assert summary["kind"] == "lectotype"
        assert summary["typifiedName"] == "Papilio pamphilus"
        assert summary["repository"] == "LSL LSL-1"
        assert summary["locality"] == "Sweden, Uppsala"
        assert summary["country"] == "SE"
        assert summary["latitude"] == 59.86

    def test_type_summary_without_a_recorded_locality(self, backbone):
        summary = detail(backbone, "Zzzonympha pamphilus")["typeSummary"]
        assert summary["kind"] == "holotype"
        assert summary["repository"] == "NHMUK"
        assert summary["locality"] is None
        assert summary["country"] is None

    def test_no_type_summary_without_types(self, backbone):
        assert detail(backbone, "Aphantopus hyperantus")["typeSummary"] is None

    def test_degrades_without_the_detail_tables(self, backbone):
        backbone.db_client.execute("DROP TABLE col_type_material")
        result = detail(backbone, "Coenonympha pamphilus")
        assert result["detailAvailable"] is False
        assert result["typeMaterial"] == []
        assert result["typeSummary"] is None
        assert result["nameUsages"][0]["name"] == "Coenonympha pamphilus"


class TestColReference:
    def test_a_trailing_link_is_dropped_from_the_citation(self):
        reference = ColReference.from_row(
            {
                "ref_citation": "Linnaeus (1758). Systema naturae. https://bhl.org/p/1",
                "ref_link": "https://bhl.org/p/1",
                "ref_issued": "1758",
            },
            "ref_",
        )
        assert reference is not None
        assert reference.citation == "Linnaeus (1758). Systema naturae."
        assert reference.link == "https://bhl.org/p/1"

    def test_nothing_to_cite(self):
        assert ColReference.from_row({}, "ref_") is None


def specimen(status, *, typifies=True, locality=None, country=None, name=None):
    return ColTypeSpecimen(
        status=status,
        typifiedName=name,
        locality=locality,
        country=country,
        typifiesSpecies=typifies,
    )


class TestTypeSummary:
    summarize = staticmethod(ColTaxonSearch._type_summary)

    def test_a_synonym_type_is_not_the_species_type(self):
        summary = self.summarize(
            [
                specimen("holotype", typifies=False, locality="Elsewhere"),
                specimen("paratype", locality="Here"),
            ]
        )
        assert summary is not None
        assert summary.kind == "paratype"
        assert summary.locality == "Here"

    def test_the_locality_falls_through_to_a_later_type(self):
        summary = self.summarize(
            [
                specimen("holotype", name="Papilio x"),
                specimen("paratype", country="SE"),
            ]
        )
        assert summary is not None
        assert summary.kind == "holotype"
        assert summary.typifiedName == "Papilio x"
        assert summary.locality is None
        assert summary.country == "SE"

    def test_only_synonym_types_give_no_summary(self):
        assert self.summarize([specimen("holotype", typifies=False)]) is None

    def test_no_types_give_no_summary(self):
        assert self.summarize([]) is None
