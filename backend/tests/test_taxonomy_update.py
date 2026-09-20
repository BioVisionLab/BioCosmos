"""Tests for the in-process taxonomy update.

The matching runs through the real colharmonize pipeline against the miniature
CoL release in tests/data/col, because the contract under test is that
pipeline's output. Faking it would test the fake.
"""

import pytest

from app.services.taxonomy_update import TaxonomyUpdateService

# Occurrences chosen to cover every display outcome.
OCCURRENCES = [
    # Accepted name, straight hit.
    (
        "img1",
        "coenonympha_pamphilus",
        "nymphalidae",
        "Animalia",
        "Arthropoda",
        "Insecta",
        "Lepidoptera",
        "species",
        "accepted",
    ),
    # Same taxon, second image: the taxon is matched once and fanned back out.
    (
        "img2",
        "coenonympha_pamphilus",
        "nymphalidae",
        "Animalia",
        "Arthropoda",
        "Insecta",
        "Lepidoptera",
        "species",
        "accepted",
    ),
    # A synonym carrying no higher taxonomy at all, as 122k occurrence rows do.
    ("img3", "papilio_pamphilus", None, None, None, None, None, "species", "synonym"),
    # Known genus, unknown epithet: colharmonize cascades to the genus stage.
    (
        "img4",
        "coenonympha_xyzzy",
        "nymphalidae",
        None,
        None,
        None,
        None,
        "species",
        "accepted",
    ),
    # Absent from CoL entirely.
    (
        "img5",
        "nonexistent_taxon",
        "nymphalidae",
        "Animalia",
        "Arthropoda",
        "Insecta",
        "Lepidoptera",
        "species",
        None,
    ),
    # An epithet two Nymphalidae genera share, under a genus spelling that
    # matches neither: the evidence cannot separate them.
    (
        "img6",
        "qqqonympha_pamphilus",
        "nymphalidae",
        None,
        None,
        None,
        None,
        "species",
        "accepted",
    ),
]

OCCURRENCE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, species VARCHAR, family VARCHAR, kingdom VARCHAR,
        phylum VARCHAR, class VARCHAR, "order" VARCHAR,
        tax_rank VARCHAR, tax_status VARCHAR
    )
"""


def seed_occurrences(client) -> None:
    client.execute(OCCURRENCE_DDL)
    for occurrence in OCCURRENCES:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            list(occurrence),
        )


def build_service(client, col_dir, tmp_path, **overrides) -> TaxonomyUpdateService:
    from pathlib import Path

    service = TaxonomyUpdateService.__new__(TaxonomyUpdateService)
    service.skip = False
    service.col_path = Path(col_dir) / "NameUsage.tsv"
    service.cache_dir = Path(tmp_path) / "cache"
    service.matches_table = "col_taxonomy_matches"
    service.candidates_table = "col_taxonomy_candidates"
    service.variants_table = "col_taxon_variants"
    service.status_table = "image_meta_taxonomy"
    service.image_meta_table = "image_meta"
    service.db_client = client
    for key, value in overrides.items():
        setattr(service, key, value)
    return service


@pytest.fixture
def harmonized(memory_duckdb, col_fixture_dir, tmp_path):
    seed_occurrences(memory_duckdb)
    service = build_service(memory_duckdb, col_fixture_dir, tmp_path)
    assert service.ensure() is True
    return memory_duckdb, service


def status_for(client, img_id: str) -> dict:
    rows = client.execute_prepared(
        "SELECT * FROM image_meta_taxonomy WHERE img_id = ?", [img_id]
    ).pl()
    return rows.to_dicts()[0]


class TestHarmonizing:
    """The whole thing happens at startup, with nothing to run by hand."""

    def test_builds_every_table(self, harmonized):
        client, _ = harmonized
        tables = set(client.table_names())
        # The variants table is what makes the per-occurrence join possible.
        assert {
            "col_taxonomy_matches",
            "col_taxonomy_candidates",
            "col_taxon_variants",
            "image_meta_taxonomy",
        } <= tables

    def test_every_occurrence_gets_a_row(self, harmonized):
        client, _ = harmonized
        occurrences, classified = client.execute(
            """
            SELECT (SELECT count(*) FROM image_meta),
                   (SELECT count(*) FROM image_meta_taxonomy)
            """
        ).fetchone()
        # A fan-out here would duplicate specimens in search results.
        assert classified == occurrences == len(OCCURRENCES)

    def test_counts_by_status(self, harmonized):
        _, service = harmonized
        counts = service.count_by_status()
        assert counts.get("MATCHED") == 4
        assert counts.get("AMBIGUOUS") == 1
        assert counts.get("UNMATCHED") == 1

    def test_occurrence_counts_are_real(self, harmonized):
        client, _ = harmonized
        # Two images share one taxon, so the matcher must see a count of two
        # rather than one row per distinct name.
        count = client.execute(
            """
            SELECT occurrence_count FROM col_taxon_variants
            WHERE original_scientific_name = 'coenonympha_pamphilus'
            """
        ).fetchone()[0]
        assert count == 2


class TestStaleness:
    def test_second_run_is_skipped(self, harmonized):
        _, service = harmonized
        assert service.ensure() is False

    def test_new_taxa_trigger_a_rematch(self, harmonized, col_fixture_dir, tmp_path):
        client, service = harmonized
        client.execute(
            "INSERT INTO image_meta VALUES "
            "('img7', 'coenonympha_tullia', 'nymphalidae', NULL, NULL, NULL, "
            "NULL, 'species', 'accepted')"
        )
        assert service.ensure() is True
        assert status_for(client, "img7")["update_status"] == "MATCHED"

    def test_more_images_of_a_known_taxon_do_not(self, harmonized):
        client, service = harmonized
        # The fingerprint is over distinct taxa, so ingesting more pictures of
        # a species already matched must not re-run the matcher.
        client.execute(
            "INSERT INTO image_meta VALUES "
            "('img8', 'coenonympha_pamphilus', 'nymphalidae', 'Animalia', "
            "'Arthropoda', 'Insecta', 'Lepidoptera', 'species', 'accepted')"
        )
        assert service.ensure() is False

    def test_dropped_tables_are_rebuilt(self, harmonized):
        client, service = harmonized
        client.execute("DROP TABLE image_meta_taxonomy")
        assert service.ensure() is True
        assert client.table_exists("image_meta_taxonomy")


class TestDisplayRule:
    def test_accepted_species_shows_the_binomial(self, harmonized):
        client, _ = harmonized
        row = status_for(client, "img1")
        assert row["update_status"] == "MATCHED"
        assert row["display_accepted_name"] == "Coenonympha pamphilus"

    def test_synonym_displays_the_accepted_name(self, harmonized):
        client, _ = harmonized
        row = status_for(client, "img3")
        # The recorded name was Papilio pamphilus; CoL accepts Coenonympha.
        assert row["match_method"] == "EXACT_SYNONYM"
        assert row["display_accepted_name"] == "Coenonympha pamphilus"

    def test_genus_only_match_shows_the_genus(self, harmonized):
        client, _ = harmonized
        row = status_for(client, "img4")
        assert row["accepted_rank"] == "genus"
        assert row["accepted_species_name"] is None
        assert row["display_accepted_name"] == "Coenonympha"

    def test_genus_cascade_keeps_its_rank_prefix(self, harmonized):
        client, _ = harmonized
        # The prefix is what the UI turns into "resolved only to genus".
        assert status_for(client, "img4")["match_method"] == "GENUS_EXACT_ACCEPTED"

    def test_ambiguous_still_names_its_leading_candidate(self, harmonized):
        client, _ = harmonized
        row = status_for(client, "img6")
        # The name is shown, but the status beside it says not to trust it;
        # the runner-up is one click away in the image metadata panel.
        assert row["update_status"] == "AMBIGUOUS"
        assert row["candidate_count"] >= 2
        assert row["display_accepted_name"] is not None

    def test_unmatched_shows_nothing(self, harmonized):
        client, _ = harmonized
        row = status_for(client, "img5")
        assert row["update_status"] == "UNMATCHED"
        assert row["display_accepted_name"] is None

    def test_repeated_images_of_one_taxon_agree(self, harmonized):
        client, _ = harmonized
        assert (
            status_for(client, "img1")["input_taxon_key"]
            == status_for(client, "img2")["input_taxon_key"]
        )


class TestGivingUpQuietly:
    """Startup must survive every way the release can be unusable."""

    def test_skip_flag(self, memory_duckdb, col_fixture_dir, tmp_path):
        seed_occurrences(memory_duckdb)
        service = build_service(memory_duckdb, col_fixture_dir, tmp_path, skip=True)
        assert service.ensure() is False
        assert "image_meta_taxonomy" not in memory_duckdb.table_names()

    def test_missing_release(self, memory_duckdb, col_fixture_dir, tmp_path):
        from pathlib import Path

        seed_occurrences(memory_duckdb)
        service = build_service(
            memory_duckdb,
            col_fixture_dir,
            tmp_path,
            col_path=Path("/nonexistent/NameUsage.tsv"),
        )
        assert service.ensure() is False

    def test_no_occurrence_table(self, memory_duckdb, col_fixture_dir, tmp_path):
        service = build_service(memory_duckdb, col_fixture_dir, tmp_path)
        assert service.ensure() is False

    def test_an_unreadable_release_does_not_raise(
        self, memory_duckdb, col_fixture_dir, tmp_path
    ):
        from pathlib import Path

        seed_occurrences(memory_duckdb)
        broken = tmp_path / "NameUsage.tsv"
        broken.write_text("not\ta\tcol\tfile\n")
        service = build_service(
            memory_duckdb, col_fixture_dir, tmp_path, col_path=Path(broken)
        )
        # Logged and skipped, not raised: this runs during startup.
        assert service.ensure() is False


class TestOccurrenceTaxonomy:
    """The per-image payload behind the Image Metadata panel."""

    @pytest.fixture
    def reader(self, harmonized):
        from app.services.taxonomy_update import OccurrenceTaxonomy

        client, _ = harmonized
        service = OccurrenceTaxonomy.__new__(OccurrenceTaxonomy)
        service.status_table = "image_meta_taxonomy"
        service.candidates_table = "col_taxonomy_candidates"
        service.image_meta_table = "image_meta"
        service.db_client = client
        return service

    def test_returns_camel_cased_keys(self, reader):
        payload = reader.get_for_image("img1")
        assert payload["updateStatus"] == "MATCHED"
        assert payload["acceptedName"] == "Coenonympha pamphilus"
        assert payload["acceptedRank"] == "species"

    def test_keeps_the_recorded_name(self, reader):
        # Shown as "Recorded as" so a reader can see why the displayed name
        # differs from the one they searched for.
        assert reader.get_for_image("img3")["inputName"] == "papilio_pamphilus"

    def test_flags_a_changed_genus(self, reader):
        payload = reader.get_for_image("img3")
        assert payload["genusChanged"] is True
        assert payload["epithetChanged"] is False

    def test_lists_alternatives_for_an_ambiguous_match(self, reader):
        payload = reader.get_for_image("img6")
        assert payload["updateStatus"] == "AMBIGUOUS"
        candidates = payload["candidates"]
        assert candidates, "an ambiguous match must show what it could not separate"
        assert all(candidate["candidateRank"] > 1 for candidate in candidates)

    def test_alternatives_exclude_the_selected_match(self, reader):
        payload = reader.get_for_image("img6")
        names = {candidate["acceptedName"] for candidate in payload["candidates"]}
        # Rank 1 is already displayed as the accepted name.
        assert payload["acceptedName"] not in names

    def test_alternatives_carry_their_evidence(self, reader):
        candidate = reader.get_for_image("img6")["candidates"][0]
        assert set(candidate) >= {
            "candidateRank",
            "acceptedName",
            "candidateMethod",
            "matchScore",
            "acceptedRank",
            "acceptedFamily",
            "genusDistance",
            "epithetDistance",
        }

    def test_decisive_match_may_still_have_runners_up(self, reader):
        payload = reader.get_for_image("img1")
        # colharmonize records the top-k candidates however decisively rank 1
        # won, so a confident match can still list weaker contenders.
        assert payload["updateStatus"] == "MATCHED"
        for candidate in payload["candidates"]:
            assert candidate["candidateRank"] > 1
            assert candidate["matchScore"] <= payload["matchScore"]

    def test_unmatched_image_still_reports_its_status(self, reader):
        payload = reader.get_for_image("img5")
        assert payload["updateStatus"] == "UNMATCHED"
        assert payload["acceptedName"] is None

    def test_unknown_image_returns_none(self, reader):
        assert reader.get_for_image("no-such-image") is None

    def test_empty_id_returns_none(self, reader):
        assert reader.get_for_image("") is None

    def test_missing_tables_return_none(self, memory_duckdb):
        from app.services.taxonomy_update import OccurrenceTaxonomy

        service = OccurrenceTaxonomy.__new__(OccurrenceTaxonomy)
        service.status_table = "image_meta_taxonomy"
        service.candidates_table = "col_taxonomy_candidates"
        service.image_meta_table = "image_meta"
        service.db_client = memory_duckdb
        # Before any run, the panel simply omits the block.
        assert service.get_for_image("img1") is None

    def test_a_missing_run_is_probed_once_not_per_image(
        self, memory_duckdb, monkeypatch
    ):
        from app.services.taxonomy_update import OccurrenceTaxonomy

        service = OccurrenceTaxonomy.__new__(OccurrenceTaxonomy)
        service.status_table = "image_meta_taxonomy"
        service.candidates_table = "col_taxonomy_candidates"
        service.image_meta_table = "image_meta"
        service.db_client = memory_duckdb

        probes = []
        original = memory_duckdb.table_exists
        monkeypatch.setattr(
            memory_duckdb,
            "table_exists",
            lambda name: (probes.append(name), original(name))[1],
        )

        def fail(*args, **kwargs):
            raise AssertionError("queried a table that is not there")

        monkeypatch.setattr(memory_duckdb, "execute_prepared_to_pl", fail)

        # The gallery fetches one image and prefetches its neighbours, so a
        # query per image means a log line per thumbnail.
        for img_id in ("img1", "img2", "img3"):
            assert service.get_for_image(img_id) is None
        assert probes == ["image_meta_taxonomy"]
