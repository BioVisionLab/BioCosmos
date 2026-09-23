"""Tests for the Catalogue of Life backbone ingest.

Exercised against a real in-memory DuckDB and a miniature ColDP release in
tests/data/col, because the behaviour under test *is* the SQL: the clade
filter, the synonym parentID closure, and name normalization.
"""

import os
from unittest.mock import patch

import pytest

from app.services.col import ColBackboneService


def build_service(duckdb_client, col_dir, **overrides):
    """Construct a ColBackboneService pointed at the fixture release."""
    service = ColBackboneService.__new__(ColBackboneService)
    service.db_client = duckdb_client
    service.path = os.path.join(col_dir, "NameUsage.tsv")
    service.vernacular_path = os.path.join(col_dir, "VernacularName.tsv")
    service.table = "col_taxonomy"
    service.vernacular_table = "col_vernacular"
    service.type_material_path = os.path.join(col_dir, "TypeMaterial.tsv")
    service.type_material_table = "col_type_material"
    service.reference_path = os.path.join(col_dir, "Reference.tsv")
    service.reference_table = "col_reference"
    service.clade_rank = "order"
    service.clade_value = "Lepidoptera"
    service.skip_ingestion = False
    for key, value in overrides.items():
        setattr(service, key, value)
    return service


@pytest.fixture
def ingested(memory_duckdb, col_fixture_dir):
    service = build_service(memory_duckdb, col_fixture_dir)
    service._ingest_name_usage()
    service._create_indexes()
    service._ingest_vernacular_names()
    service._ingest_type_material()
    service._ingest_references()
    return memory_duckdb, service


def usage_ids(client) -> set[str]:
    rows = client.execute("SELECT usage_id FROM col_taxonomy").fetchall()
    return {row[0] for row in rows}


class TestCladeFilter:
    def test_keeps_taxa_inside_the_clade(self, ingested):
        client, _ = ingested
        assert {"AAA1", "AAA2", "AAA3", "GEN1"} <= usage_ids(client)

    def test_excludes_taxa_outside_the_clade(self, ingested):
        client, _ = ingested
        # Carabus is Coleoptera; neither it nor its synonym belongs here.
        assert "BEE1" not in usage_ids(client)
        assert "BSYN" not in usage_ids(client)

    def test_drops_unranked_rows(self, ingested):
        client, _ = ingested
        assert "UNR1" not in usage_ids(client)

    def test_no_clade_filter_ingests_everything(self, memory_duckdb, col_fixture_dir):
        service = build_service(
            memory_duckdb, col_fixture_dir, clade_rank=None, clade_value=None
        )
        service._ingest_name_usage()
        # The beetle and its synonym now survive; the unranked row still does not.
        ids = usage_ids(memory_duckdb)
        assert "BEE1" in ids and "BSYN" in ids
        assert "UNR1" not in ids

    def test_unknown_clade_rank_is_rejected(self, memory_duckdb, col_fixture_dir):
        service = build_service(memory_duckdb, col_fixture_dir, clade_rank="borough")
        with pytest.raises(ValueError, match="Unknown CoL clade_rank"):
            service._ingest_name_usage()


class TestSynonymClosure:
    def test_synonym_inside_the_clade_is_kept(self, ingested):
        client, _ = ingested
        # SYN1 carries no lineage of its own, so only the parentID pass can
        # bring it in. Without it, searching the synonym would find nothing.
        assert "SYN1" in usage_ids(client)

    def test_synonym_resolves_to_its_accepted_taxon(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT accepted_id, is_accepted FROM col_taxonomy WHERE usage_id = 'SYN1'"
        ).fetchone()
        assert row == ("AAA1", False)

    def test_accepted_taxon_points_at_itself(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT accepted_id, is_accepted FROM col_taxonomy WHERE usage_id = 'AAA1'"
        ).fetchone()
        assert row == ("AAA1", True)

    def test_provisionally_accepted_counts_as_accepted(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT accepted_id, is_accepted FROM col_taxonomy WHERE usage_id = 'AAA2'"
        ).fetchone()
        assert row == ("AAA2", True)

    def test_no_row_is_duplicated_by_the_union(self, ingested):
        client, _ = ingested
        total, distinct = client.execute(
            "SELECT count(*), count(DISTINCT usage_id) FROM col_taxonomy"
        ).fetchone()
        assert total == distinct


class TestNormalization:
    def test_name_norm_matches_the_occurrence_key(self, ingested):
        client, _ = ingested
        # image_meta stores 'coenonympha_pamphilus'; sanitize_species_name turns
        # that into 'coenonympha pamphilus', which must find this row.
        row = client.execute_prepared(
            "SELECT usage_id FROM col_taxonomy WHERE name_norm = ?",
            ["coenonympha pamphilus"],
        ).fetchone()
        assert row[0] == "AAA1"

    def test_name_norm_collapses_repeated_whitespace(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT name_norm FROM col_taxonomy WHERE usage_id = 'AAA3'"
        ).fetchone()
        assert row[0] == "coenonympha tullia"

    def test_rank_is_lowercased(self, ingested):
        client, _ = ingested
        ranks = client.execute(
            "SELECT DISTINCT taxon_rank FROM col_taxonomy"
        ).fetchall()
        assert all(rank[0] == rank[0].lower() for rank in ranks)

    def test_lineage_is_carried_through(self, ingested):
        client, _ = ingested
        row = client.execute(
            """
            SELECT kingdom, phylum, class, "order", superfamily, family,
                   subfamily, tribe, genus
            FROM col_taxonomy WHERE usage_id = 'AAA1'
            """
        ).fetchone()
        assert row == (
            "Animalia",
            "Arthropoda",
            "Insecta",
            "Lepidoptera",
            "Papilionoidea",
            "Nymphalidae",
            "Satyrinae",
            "Coenonymphini",
            "Coenonympha",
        )


class TestVernacularNames:
    def test_prefers_the_english_name(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT vernacular_name, language FROM col_vernacular WHERE usage_id = 'AAA1'"
        ).fetchone()
        assert row == ("Small heath", "eng")

    def test_one_name_per_usage(self, ingested):
        client, _ = ingested
        total, distinct = client.execute(
            "SELECT count(*), count(DISTINCT usage_id) FROM col_vernacular"
        ).fetchone()
        assert total == distinct

    def test_excludes_names_for_taxa_outside_the_clade(self, ingested):
        client, _ = ingested
        rows = client.execute(
            "SELECT usage_id FROM col_vernacular WHERE usage_id = 'BEE1'"
        ).fetchall()
        assert rows == []

    def test_missing_file_yields_an_empty_table(self, memory_duckdb, col_fixture_dir):
        service = build_service(
            memory_duckdb,
            col_fixture_dir,
            vernacular_path="/nonexistent/Vernacular.tsv",
        )
        service._ingest_name_usage()
        service._ingest_vernacular_names()
        # An empty table, not a crash: common names fall back to image_meta.
        assert (
            memory_duckdb.execute("SELECT count(*) FROM col_vernacular").fetchone()[0]
            == 0
        )


class TestTypeMaterial:
    def test_keeps_types_of_names_inside_the_clade(self, ingested):
        client, _ = ingested
        rows = client.execute(
            "SELECT name_id, status FROM col_type_material ORDER BY name_id, status"
        ).fetchall()
        # BEE1 is a beetle, so its holotype is dropped with it.
        assert rows == [
            ("BBB1", "holotype"),
            ("SYN1", "lectotype"),
            ("SYN1", "paralectotype"),
        ]

    def test_blank_fields_are_null(self, ingested):
        client, _ = ingested
        (host,) = client.execute(
            "SELECT host FROM col_type_material WHERE name_id = 'BBB1'"
        ).fetchone()
        assert host is None

    def test_missing_file_yields_an_empty_table(self, memory_duckdb, col_fixture_dir):
        service = build_service(
            memory_duckdb,
            col_fixture_dir,
            type_material_path="/nonexistent/TypeMaterial.tsv",
        )
        service._ingest_name_usage()
        service._ingest_type_material()
        assert (
            memory_duckdb.execute("SELECT count(*) FROM col_type_material").fetchone()[
                0
            ]
            == 0
        )


class TestReferences:
    def test_keeps_only_cited_references(self, ingested):
        client, _ = ingested
        rows = client.execute(
            "SELECT reference_id FROM col_reference ORDER BY reference_id"
        ).fetchall()
        # REF1 and REF2 are cited by names, REF3 by a type specimen; REF9 by
        # nothing.
        assert [row[0] for row in rows] == ["REF1", "REF2", "REF3"]

    def test_name_reference_is_carried_on_the_usage(self, ingested):
        client, _ = ingested
        row = client.execute(
            "SELECT name_reference_id, name_published_in_page FROM col_taxonomy "
            "WHERE usage_id = 'SYN1'"
        ).fetchone()
        assert row == ("REF1", "472")


class TestIngestGuards:
    def test_skip_flag_short_circuits(self, memory_duckdb, col_fixture_dir):
        service = build_service(memory_duckdb, col_fixture_dir, skip_ingestion=True)
        service.ingest()
        assert "col_taxonomy" not in memory_duckdb.table_names()

    def test_missing_source_is_logged_not_raised(self, memory_duckdb, col_fixture_dir):
        service = build_service(
            memory_duckdb, col_fixture_dir, path="/nonexistent/NameUsage.tsv"
        )
        service.ingest()
        assert "col_taxonomy" not in memory_duckdb.table_names()

    def test_second_ingest_is_skipped_when_unchanged(
        self, memory_duckdb, col_fixture_dir
    ):
        service = build_service(memory_duckdb, col_fixture_dir)
        service.ingest()
        first = memory_duckdb.execute("SELECT count(*) FROM col_taxonomy").fetchone()[0]

        with patch.object(
            ColBackboneService,
            "_ingest_name_usage",
            side_effect=AssertionError("reloaded"),
        ):
            service.ingest()

        assert (
            memory_duckdb.execute("SELECT count(*) FROM col_taxonomy").fetchone()[0]
            == first
        )

    def test_a_database_without_the_detail_tables_is_rebuilt(
        self, memory_duckdb, col_fixture_dir
    ):
        service = build_service(memory_duckdb, col_fixture_dir)
        service.ingest()
        # As a database built before type material was ingested would be.
        memory_duckdb.execute("DROP TABLE col_type_material")

        service.ingest()
        assert memory_duckdb.table_exists("col_type_material")

    def test_changed_source_triggers_a_reload(
        self, memory_duckdb, col_fixture_dir, tmp_path
    ):
        import shutil

        release = tmp_path / "col"
        shutil.copytree(col_fixture_dir, release)
        service = build_service(memory_duckdb, str(release))
        service.ingest()

        # Append a new Lepidoptera species, which changes size and mtime.
        usage = release / "NameUsage.tsv"
        columns = usage.read_text().splitlines()[0].split("\t")
        new = {
            "col:ID": "AAA9",
            "col:parentID": "GEN1",
            "col:status": "accepted",
            "col:scientificName": "Coenonympha nova",
            "col:rank": "species",
            "col:genus": "Coenonympha",
            "col:family": "Nymphalidae",
            "col:order": "Lepidoptera",
        }
        with usage.open("a") as handle:
            handle.write("\t".join(new.get(name, "") for name in columns) + "\n")

        service.ingest()
        assert "AAA9" in usage_ids(memory_duckdb)
