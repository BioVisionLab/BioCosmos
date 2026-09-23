"""Database-grounded common-name search, without model or network calls."""

import pytest
from app.services.common_names import CommonNameSearch


@pytest.fixture
def search(memory_duckdb):
    memory_duckdb.execute("""
        CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR, common_name VARCHAR);
        INSERT INTO image_meta VALUES
            ('a', 'danaus_plexippus', ' Monarch '),
            ('b', 'danaus_plexippus', 'monarch'),
            ('c', 'danaus_erippus', 'Southern Monarch'),
            ('d', 'species_shared', 'MONARCH'),
            ('e', 'species_false', 'Monarchist'),
            ('f', 'species_special', '100% O''Brien_(blue)'),
            ('g', 'morpho_helenor', NULL),
            ('h', 'old_synonym', NULL),
            ('i', 'species_spacing', '  blue   moon  ');
    """)
    service = CommonNameSearch(memory_duckdb)
    service.image_table = "image_meta"
    service.backbone_table = "col_taxonomy"
    service.vernacular_table = "col_vernacular"
    service.taxonomy_table = "image_meta_taxonomy"
    return service


def test_exact_shared_names_are_deduplicated_and_preferred(search):
    assert search.search("  MONARCH  ") == ["danaus_plexippus", "species_shared"]


def test_partial_phrase_obeys_word_boundaries(search):
    assert search.search("southern") == ["danaus_erippus"]
    assert search.search("mon") == []
    search.db_client.execute(
        "DELETE FROM image_meta WHERE lower(trim(common_name)) = 'monarch'"
    )
    assert search.search("monarch") == ["danaus_erippus"]


def test_whitespace_and_literal_metacharacters(search):
    assert search.search(" Blue\tMOON ") == ["species_spacing"]
    assert search.search("100% O'Brien_(blue)") == ["species_special"]
    assert search.search("O'Brien_(blue)") == ["species_special"]
    assert search.search("' OR 1=1 --") == []
    assert search.search("%") == []


@pytest.mark.parametrize("name", ["", "   ", "unrecorded butterfly"])
def test_unmatched_names(search, name):
    assert search.search(name) == []


def test_vernacular_and_harmonized_names_resolve_to_image_species(search):
    search.db_client.execute("""
        CREATE TABLE col_taxonomy
            (usage_id VARCHAR, accepted_id VARCHAR, canonical_key VARCHAR);
        INSERT INTO col_taxonomy VALUES ('m', 'm', 'morpho helenor');
        CREATE TABLE col_vernacular (usage_id VARCHAR, vernacular_name VARCHAR);
        INSERT INTO col_vernacular VALUES ('m', 'Blue Morpho'), ('absent', 'Ghost');
        CREATE TABLE image_meta_taxonomy (img_id VARCHAR, accepted_id VARCHAR);
        INSERT INTO image_meta_taxonomy VALUES ('h', 'm');
    """)
    assert search.search("blue morpho") == ["morpho_helenor", "old_synonym"]
    assert search.search("morpho") == ["morpho_helenor", "old_synonym"]
    assert search.search("ghost") == []
    assert search.search("monarch") == ["danaus_plexippus", "species_shared"]


def test_exact_precedence_across_sources(search):
    search.db_client.execute("""
        CREATE TABLE col_vernacular (usage_id VARCHAR, vernacular_name VARCHAR);
        INSERT INTO col_vernacular VALUES ('m', 'Southern');
        CREATE TABLE image_meta_taxonomy (img_id VARCHAR, accepted_id VARCHAR);
        INSERT INTO image_meta_taxonomy VALUES ('g', 'm');
    """)
    assert search.search("southern") == ["morpho_helenor"]
