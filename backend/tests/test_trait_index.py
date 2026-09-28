"""Tests for the LepTraits index and the two searches that filter on it.

Run against a real in-memory DuckDB, because the behaviour under test is the
SQL: how a LepTraits name is resolved to the collection's accepted species,
and which recorded names a trait filter returns.
"""

from unittest.mock import MagicMock

import pytest

from app.query.db_search import TextToDbSearch
from app.services.agent import AgentSearchService, trait_predicate
from app.services.agent_tools import TraitArgs
from app.services.leptraits import LepTraits, TraitIndexService
from app.services.metadata import (
    SPECIMEN_COLUMNS,
    SPECIMEN_TAXONOMY_COLUMNS,
    ImageMetaService,
)

MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
TRAIT_COLUMNS = (
    "Species",
    "WS_U",
    "CanopyAffinity",
    "MoistureAffinity",
    "Voltinism",
    "DiapauseStage",
    "OvipositionStyle",
    "NumberOfHostplantFamilies",
    "SoleHostplantFamily",
    "PrimaryHostplantFamily",
    *MONTHS,
)


def _months(*flying: str) -> tuple[str, ...]:
    return tuple("1" if month in flying else "0" for month in MONTHS)


# As the consensus file writes them: text throughout, 'NA' for missing.
LEPTRAITS = [
    # Two rows for one species; the second supplies what the first lacks.
    ("Danaus plexippus", "10.5", "Open canopy", "NA", "M", "NA", "NA", "1", "NA",
     "Apocynaceae", *_months("Jun", "Jul", "Aug")),
    ("Danaus plexippus", "NA", "NA", "NA", "NA", "A", "NA", "NA", "NA", "NA",
     *("NA",) * 12),
    # A synonym: CoL accepts it as Heliconius charithonia.
    ("Heliconius charitonia", "7", "Closed canopy", "NA", "U", "PL", "S,C", "1",
     "Passifloraceae", "NA", *_months("Jan")),
    # CoL writes it with a subgenus, so only its canonical form matches.
    ("Morpho peleides", "12", "Mixed canopy (closed affinity)",
     "Mesic-associated (weak)", "B", "NA", "S", "4", "NA", "Fabaceae",
     *_months("Jun")),
    # Not in the collection.
    ("Absentia nullus", "3", "Closed canopy", "NA", "U", "NA", "NA", "NA", "NA",
     "NA", *_months()),
]  # fmt: skip

# usage_id, name_norm, canonical_key, is_accepted, accepted_id, genus, epithet
BACKBONE = [
    ("c1", "danaus plexippus", "danaus plexippus", True, "c1", "danaus", "plexippus"),
    ("c2", "heliconius charithonia", "heliconius charithonia", True, "c2",
     "heliconius", "charithonia"),
    ("c3", "heliconius charitonia", "heliconius charitonia", False, "c2",
     "heliconius", "charitonia"),
    ("c4", "morpho (morpho) peleides", "morpho peleides", True, "c4", "morpho",
     "peleides"),
]  # fmt: skip

# img_id -> (recorded species, update_status, accepted_species_name)
OCCURRENCES = {
    "img1": ("danaus_plexippus", "MATCHED", "Danaus plexippus"),
    "img2": ("danaus_plexippus_plexippus", "MATCHED", "Danaus plexippus"),
    "img3": ("heliconius_charithonia", "MATCHED", "Heliconius charithonia"),
    # A misspelling the harmonization run folded into the accepted species.
    "img4": ("heliconius_charitonius", "MATCHED", "Heliconius charithonia"),
    "img5": ("morpho_peleides", "MATCHED", "Morpho peleides"),
    "img6": ("unresolvable_name", "UNMATCHED", None),
}


def _seed(client, *, backbone=True, status=True) -> None:
    columns = ", ".join(f'"{column}" VARCHAR' for column in TRAIT_COLUMNS)
    client.execute(f"CREATE TABLE lep_traits_consensus ({columns})")
    placeholders = ", ".join("?" for _ in TRAIT_COLUMNS)
    for row in LEPTRAITS:
        client.execute_prepared(
            f"INSERT INTO lep_traits_consensus VALUES ({placeholders})", list(row)
        )

    # Every column a specimen listing selects, so the text search can run.
    occurrence_columns = ", ".join(
        f'"{column}" {"DOUBLE" if column in ("lat", "lon") else "VARCHAR"}'
        for column in SPECIMEN_COLUMNS
    )
    client.execute(f"CREATE TABLE image_meta ({occurrence_columns})")
    for img_id, (species, _, _) in OCCURRENCES.items():
        client.execute_prepared(
            "INSERT INTO image_meta (img_id, species) VALUES (?, ?)", [img_id, species]
        )

    if status:
        taxonomy_columns = ", ".join(
            f'"{column}" VARCHAR' for column in SPECIMEN_TAXONOMY_COLUMNS
        )
        client.execute(
            f"CREATE TABLE image_meta_taxonomy (img_id VARCHAR, "
            f"accepted_species_name VARCHAR, {taxonomy_columns})"
        )
        for img_id, (_, update_status, accepted) in OCCURRENCES.items():
            client.execute_prepared(
                "INSERT INTO image_meta_taxonomy (img_id, update_status, "
                "accepted_species_name, accepted_name, accepted_family) "
                "VALUES (?, ?, ?, ?, 'Nymphalidae')",
                [img_id, update_status, accepted, accepted],
            )

    if backbone:
        client.execute(
            "CREATE TABLE col_taxonomy (usage_id VARCHAR, name_norm VARCHAR, "
            "canonical_key VARCHAR, is_accepted BOOLEAN, accepted_id VARCHAR, "
            "genus_norm VARCHAR, epithet_norm VARCHAR)"
        )
        for row in BACKBONE:
            client.execute_prepared(
                "INSERT INTO col_taxonomy VALUES (?, ?, ?, ?, ?, ?, ?)", list(row)
            )


def _index(client) -> dict[str, dict]:
    rows = client.execute("SELECT * FROM image_meta_traits").pl().to_dicts()
    return {row["img_id"]: row for row in rows}


@pytest.fixture
def indexed(memory_duckdb):
    _seed(memory_duckdb)
    assert TraitIndexService(memory_duckdb).ensure()
    return memory_duckdb


class TestTraitIndex:
    def test_covers_every_image_of_each_accepted_species(self, indexed):
        # The trinomial, the misspelling and the synonym all resolve; the
        # unmatched record and the species absent from the collection do not.
        assert set(_index(indexed)) == {"img1", "img2", "img3", "img4", "img5"}

    def test_a_synonym_resolves_to_the_accepted_species(self, indexed):
        rows = _index(indexed)
        assert rows["img4"]["trait_species"] == "heliconius charithonia"
        assert rows["img4"]["leptraits_name"] == "heliconius charitonia"
        assert rows["img4"]["canopy_affinity"] == "Closed canopy"

    def test_a_subgenus_name_resolves_through_its_canonical_form(self, indexed):
        assert _index(indexed)["img5"]["trait_species"] == "morpho peleides"

    def test_duplicate_rows_collapse_to_one_filling_gaps(self, indexed):
        rows = _index(indexed)
        count = indexed.execute("SELECT count(*) FROM image_meta_traits").fetchone()
        assert count[0] == len(rows)
        danaus = rows["img1"]
        assert danaus["canopy_affinity"] == "Open canopy"
        assert danaus["diapause_stage"] == "Adult"

    def test_na_is_null(self, indexed):
        assert _index(indexed)["img1"]["moisture_affinity"] is None

    def test_codes_are_decoded_to_words(self, indexed):
        rows = _index(indexed)
        heliconius, danaus, morpho = rows["img3"], rows["img1"], rows["img5"]
        assert heliconius["voltinism"] == "Univoltine"
        assert heliconius["diapause_stage"] == "Larva, Pupa"
        assert heliconius["oviposition_style"] == "Single, Clustered"
        assert heliconius["hostplant_families"] == "Passifloraceae"
        assert heliconius["host_breadth"] == "Specialist"
        assert heliconius["flight_months"] == "Jan"
        assert danaus["voltinism"] == "Multivoltine"
        assert danaus["flight_months"] == "Jun, Jul, Aug"
        assert morpho["host_breadth"] == "Generalist"

    def test_wing_size_is_relative_to_the_collection(self, indexed):
        rows = _index(indexed)
        # 7, 10.5 and 12 cm: terciles of the species held, not of LepTraits.
        assert rows["img3"]["wing_size"] == "Small"
        assert rows["img1"]["wing_size"] == "Medium"
        assert rows["img5"]["wing_size"] == "Large"

    def test_an_unchanged_source_is_not_rebuilt(self, indexed):
        assert not TraitIndexService(indexed).ensure()

    def test_a_changed_source_is_rebuilt(self, indexed):
        indexed.execute(
            "INSERT INTO image_meta (img_id, species) VALUES ('img7', 'morpho_peleides')"
        )
        indexed.execute(
            "INSERT INTO image_meta_taxonomy (img_id, update_status, "
            "accepted_species_name) VALUES ('img7', 'MATCHED', 'Morpho peleides')"
        )
        assert TraitIndexService(indexed).ensure()
        assert "img7" in _index(indexed)

    def test_without_a_backbone_names_join_as_written(self, memory_duckdb):
        _seed(memory_duckdb, backbone=False)
        assert TraitIndexService(memory_duckdb).ensure()
        # The synonym no longer resolves; exact names still do.
        assert set(_index(memory_duckdb)) == {"img1", "img2", "img5"}

    def test_without_a_run_the_recorded_binomial_is_used(self, memory_duckdb):
        _seed(memory_duckdb, status=False)
        assert TraitIndexService(memory_duckdb).ensure()
        assert set(_index(memory_duckdb)) == {"img1", "img2", "img3", "img5"}

    def test_missing_leptraits_skips_without_raising(self, memory_duckdb):
        memory_duckdb.execute(
            "CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR)"
        )
        assert not TraitIndexService(memory_duckdb).ensure()


class TestTraitPredicate:
    def test_a_category_expands_to_every_recorded_grade(self):
        sql, params = trait_predicate("moisture", "wet")
        assert sql == "t.moisture_affinity IN (?, ?)"
        assert params == ["Mesic-associated (strong)", "Mesic-associated (weak)"]

    def test_months_match_any(self):
        sql, params = trait_predicate("flight_months", ["jun", "jul"])
        assert " OR " in sql
        assert params == ["jun", "jul"]

    def test_unknown_argument_is_rejected(self):
        with pytest.raises(ValueError):
            trait_predicate("colour", "blue")


def _agent(client) -> AgentSearchService:
    service = AgentSearchService.__new__(AgentSearchService)
    service.leptraits_service = LepTraits(client)
    service.image_meta_service = ImageMetaService(client)
    return service


class TestAgentTraitSearch:
    @pytest.mark.asyncio
    async def test_returns_every_recorded_name_of_a_matching_species(self, indexed):
        rows = await _agent(indexed)._search_by_traits(TraitArgs(canopy="closed"))
        assert {row["species"] for row in rows} == {
            "heliconius_charithonia",
            "heliconius_charitonius",
            "morpho_peleides",
        }
        assert {row["tool_names"] for row in rows} == {"search_by_traits"}

    @pytest.mark.asyncio
    async def test_constraints_combine(self, indexed):
        # "June" goes through the model's before-validator, as planner output does.
        args = TraitArgs.model_validate(
            {
                "canopy": "closed",
                "hostplant_family": "fabaceae",
                "flight_months": ["June"],
            }
        )
        rows = await _agent(indexed)._search_by_traits(args)
        assert {row["species"] for row in rows} == {"morpho_peleides"}

    @pytest.mark.asyncio
    async def test_a_species_absent_from_the_collection_is_not_returned(self, indexed):
        rows = await _agent(indexed)._search_by_traits(
            TraitArgs(voltinism="univoltine")
        )
        assert {row["species"] for row in rows} == {
            "heliconius_charithonia",
            "heliconius_charitonius",
        }

    @pytest.mark.asyncio
    async def test_a_missing_index_fails_rather_than_matching_nothing(
        self, memory_duckdb
    ):
        _seed(memory_duckdb)
        with pytest.raises(RuntimeError):
            await _agent(memory_duckdb)._search_by_traits(TraitArgs(canopy="open"))


def _request(client):
    request = MagicMock()
    request.app.state.duck_db = client
    return request


class TestTextTraitSearch:
    def test_a_trait_field_returns_normalized_species(self, indexed):
        result = TextToDbSearch(
            request=_request(indexed), query="closed", field="canopy_affinity"
        ).search()
        assert result is not None
        # Both spellings of Heliconius charithonia land on its one page.
        assert sorted(row["species"] for row in result["results"]) == [
            "heliconius_charithonia",
            "morpho_peleides",
        ]
        by_id = {row["img_id"]: row for row in result["specimens"]}
        assert set(by_id) == {"img3", "img4", "img5"}
        assert by_id["img4"]["canopy_affinity"] == "Closed canopy"
        assert by_id["img4"]["matched_fields"] == ["canopy_affinity"]

    def test_host_plant_family(self, indexed):
        result = TextToDbSearch(
            request=_request(indexed), query="apocynaceae", field="hostplant_families"
        ).search()
        assert result is not None
        assert [row["species"] for row in result["results"]] == ["danaus_plexippus"]

    def test_traits_stay_out_of_the_all_fields_sweep(self, indexed):
        result = TextToDbSearch(
            request=_request(indexed), query="closed canopy", field="all"
        ).search()
        assert result is not None
        assert result["results"] == []

    def test_before_the_index_exists_a_trait_search_is_empty(self, memory_duckdb):
        _seed(memory_duckdb)
        result = TextToDbSearch(
            request=_request(memory_duckdb), query="closed", field="canopy_affinity"
        ).search()
        assert result is not None
        assert result["results"] == []


class TestSpeciesPageTraits:
    def test_a_name_leptraits_uses_is_found_directly(self, indexed):
        traits = LepTraits(indexed).get("morpho_peleides")
        assert traits["canopy_affinity"] == "Mixed canopy (closed affinity)"

    def test_the_page_key_finds_traits_filed_under_a_synonym(self, indexed):
        # LepTraits calls it Heliconius charitonia; the page does not.
        for name in ("heliconius_charithonia", "heliconius_charitonius"):
            assert LepTraits(indexed).get(name)["canopy_affinity"] == "Closed canopy"

    def test_a_species_leptraits_lacks_has_none(self, indexed):
        assert LepTraits(indexed).get("unresolvable_name") == {}

    def test_without_the_index_only_exact_names_match(self, memory_duckdb):
        _seed(memory_duckdb)
        service = LepTraits(memory_duckdb)
        assert service.get("heliconius_charithonia") == {}
        assert (
            service.get("Heliconius charitonia")["canopy_affinity"] == "Closed canopy"
        )

    def test_the_name_is_bound_not_interpolated(self, indexed):
        assert LepTraits(indexed).get("x') OR ('1'='1") == {}
