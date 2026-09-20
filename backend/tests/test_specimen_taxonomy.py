"""Tests for the taxonomy columns on specimen search results.

The join is optional by construction: image_meta_taxonomy only exists once a
colharmonize run has been loaded, and search has to keep working before that.
Both paths are covered here because a missing table would otherwise take the
whole search endpoint down with a SQL error.
"""

import pytest

from app.services.metadata import (
    SPECIMEN_TAXONOMY_COLUMNS,
    ImageMetaService,
)

OCCURRENCE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, species VARCHAR, family VARCHAR, common_name VARCHAR,
        sex VARCHAR, life_stage VARCHAR, class_dv VARCHAR,
        lat DOUBLE, lon DOUBLE, source_db VARCHAR,
        kingdom VARCHAR, phylum VARCHAR, class VARCHAR, "order" VARCHAR
    )
"""

TAXONOMY_DDL = """
    CREATE TABLE image_meta_taxonomy (
        img_id VARCHAR, input_taxon_key VARCHAR, update_status VARCHAR,
        match_method VARCHAR, accepted_id VARCHAR, accepted_name VARCHAR,
        accepted_species_name VARCHAR, accepted_rank VARCHAR,
        accepted_authorship VARCHAR, accepted_family VARCHAR,
        accepted_status VARCHAR, match_score INTEGER, score_margin INTEGER,
        candidate_count INTEGER, genus_changed BOOLEAN, epithet_changed BOOLEAN,
        reason_code VARCHAR, display_accepted_name VARCHAR
    )
"""


def seed_occurrences(client) -> None:
    client.execute(OCCURRENCE_DDL)
    for img_id, species in [
        ("i1", "coenonympha_pamphilus"),
        ("i2", "papilio_pamphilus"),
        ("i3", "nonexistent_taxon"),
    ]:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, 'nymphalidae', NULL, NULL, NULL,"
            " 'dorsal', 1.0, 2.0, 'gbif', 'Animalia', 'Arthropoda', 'Insecta',"
            " 'Lepidoptera')",
            [img_id, species],
        )


def seed_taxonomy(client) -> None:
    client.execute(TAXONOMY_DDL)
    rows = [
        # Matched to an accepted species.
        (
            "i1",
            "k1",
            "MATCHED",
            "EXACT_ACCEPTED",
            "AAA1",
            "Coenonympha pamphilus",
            "Coenonympha pamphilus",
            "species",
            "(Linnaeus, 1758)",
            "Nymphalidae",
            "accepted",
            7400,
            900,
            1,
            False,
            False,
            None,
            "Coenonympha pamphilus",
        ),
        # A synonym resolved to the same accepted taxon.
        (
            "i2",
            "k2",
            "MATCHED",
            "EXACT_SYNONYM",
            "AAA1",
            "Coenonympha pamphilus",
            "Coenonympha pamphilus",
            "species",
            "(Linnaeus, 1758)",
            "Nymphalidae",
            "accepted",
            6400,
            500,
            1,
            True,
            False,
            None,
            "Coenonympha pamphilus",
        ),
        # No match at all: every accepted field stays null.
        (
            "i3",
            "k3",
            "UNMATCHED",
            "UNMATCHED",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            False,
            False,
            None,
            None,
        ),
    ]
    for row in rows:
        placeholders = ", ".join("?" for _ in row)
        client.execute_prepared(
            f"INSERT INTO image_meta_taxonomy VALUES ({placeholders})", list(row)
        )


def build_service(client) -> ImageMetaService:
    service = ImageMetaService.__new__(ImageMetaService)
    service.table = "image_meta"
    service.taxonomy_table = "image_meta_taxonomy"
    service._taxonomy_table_present = None
    service.db_client = client
    return service


@pytest.fixture
def with_taxonomy(memory_duckdb):
    seed_occurrences(memory_duckdb)
    seed_taxonomy(memory_duckdb)
    return build_service(memory_duckdb)


@pytest.fixture
def without_taxonomy(memory_duckdb):
    seed_occurrences(memory_duckdb)
    return build_service(memory_duckdb)


class TestWithTaxonomy:
    def test_detects_the_table(self, with_taxonomy):
        assert with_taxonomy._taxonomy_available() is True

    def test_specimens_carry_the_update(self, with_taxonomy):
        _, specimens, total = with_taxonomy.search_by_field(
            "species", "%coenonympha%", 50, 0
        )
        assert total == 1
        row = specimens.to_dicts()[0]
        assert row["update_status"] == "MATCHED"
        assert row["display_accepted_name"] == "Coenonympha pamphilus"

    def test_synonym_row_shows_the_accepted_name(self, with_taxonomy):
        _, specimens, _ = with_taxonomy.search_by_field("species", "%papilio%", 50, 0)
        row = specimens.to_dicts()[0]
        assert row["species"] == "papilio_pamphilus"
        assert row["display_accepted_name"] == "Coenonympha pamphilus"
        assert row["match_method"] == "EXACT_SYNONYM"

    def test_unmatched_row_has_no_accepted_name(self, with_taxonomy):
        _, specimens, _ = with_taxonomy.search_by_field(
            "species", "%nonexistent%", 50, 0
        )
        row = specimens.to_dicts()[0]
        assert row["update_status"] == "UNMATCHED"
        assert row["display_accepted_name"] is None

    def test_status_is_filterable(self, with_taxonomy):
        _, specimens, total = with_taxonomy.search_by_field(
            "update_status", "%UNMATCHED%", 50, 0
        )
        assert total == 1
        assert specimens["img_id"].to_list() == ["i3"]

    def test_join_does_not_inflate_the_count(self, with_taxonomy):
        _, specimens, total = with_taxonomy.search_all_fields(
            ["family", "species"], "%nymphalidae%", 50, 0
        )
        # One row per occurrence, not one per occurrence-times-match.
        assert total == 3
        assert len(specimens) == 3

    def test_coordinate_search_carries_the_update(self, with_taxonomy):
        _, specimens, total = with_taxonomy.search_by_coordinate(
            0.0, 2.0, 1.0, 3.0, 50, 0
        )
        assert total == 3
        assert set(specimens["update_status"].to_list()) == {"MATCHED", "UNMATCHED"}


class TestWithoutTaxonomy:
    """Before any colharmonize run has been loaded."""

    def test_detects_the_absence(self, without_taxonomy):
        assert without_taxonomy._taxonomy_available() is False

    @pytest.mark.parametrize(
        "search",
        [
            lambda s: s.search_by_field("species", "%coenonympha%", 50, 0),
            lambda s: s.search_all_fields(
                ["family", "species"], "%nymphalidae%", 50, 0
            ),
            lambda s: s.search_by_coordinate(0.0, 2.0, 1.0, 3.0, 50, 0),
        ],
        ids=["by_field", "all_fields", "by_coordinate"],
    )
    def test_search_still_works(self, without_taxonomy, search):
        _, specimens, total = search(without_taxonomy)
        assert total >= 1
        assert not specimens.is_empty()

    def test_payload_keeps_its_shape(self, without_taxonomy):
        _, specimens, _ = without_taxonomy.search_by_field(
            "species", "%coenonympha%", 50, 0
        )
        # The columns are present and null, so the client needs no second shape.
        for column in SPECIMEN_TAXONOMY_COLUMNS:
            assert column in specimens.columns
            assert specimens[column].to_list() == [None]
