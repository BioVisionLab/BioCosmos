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

    def test_reads_without_the_occurrence_table(self, harmonized, reader):
        """The recorded name comes off the status table now.

        Pinned because the panel would otherwise lose its "Recorded as" line
        silently if the column stopped being written.
        """
        client, _ = harmonized
        client.execute("DROP TABLE image_meta")
        assert reader.get_for_image("img3")["inputName"] == "papilio_pamphilus"

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


class TestRecordedColumns:
    """The status table carries what the occurrence itself said."""

    def test_stores_the_recorded_name(self, harmonized):
        client, _ = harmonized
        assert status_for(client, "img3")["recorded_name"] == "papilio_pamphilus"

    def test_recorded_rank_is_not_the_accepted_rank(self, harmonized):
        """img4 cascades to a genus, but the occurrence still said species.

        The two ranks answer different questions — what was written down, and
        what it resolved to — so they must not be conflated.
        """
        client, _ = harmonized
        row = status_for(client, "img4")
        assert row["recorded_rank"] == "species"
        assert row["accepted_rank"] == "genus"

    def test_degrades_when_the_occurrence_has_no_rank_column(
        self, memory_duckdb, col_fixture_dir, tmp_path
    ):
        """Ingestion can be skipped, so tax_rank is not guaranteed."""
        memory_duckdb.execute(
            """
            CREATE TABLE image_meta (
                img_id VARCHAR, species VARCHAR, family VARCHAR, kingdom VARCHAR,
                phylum VARCHAR, class VARCHAR, "order" VARCHAR
            )
            """
        )
        for occurrence in OCCURRENCES:
            memory_duckdb.execute_prepared(
                "INSERT INTO image_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                list(occurrence[:7]),
            )
        service = build_service(memory_duckdb, col_fixture_dir, tmp_path)
        assert service.ensure() is True
        ranks = memory_duckdb.execute(
            "SELECT DISTINCT recorded_rank FROM image_meta_taxonomy"
        ).pl()
        assert ranks["recorded_rank"].to_list() == [None]

    def test_a_stale_shaped_table_is_rebuilt(self, harmonized):
        """The marker can outlive the table it describes.

        Seen for real: a reload picked up the version bump before the column
        change, so the run recorded the new fingerprint against a table built
        the old way. Everything else then said "current" and the panel served
        nulls. The shape of the table has to be checked, not just its name.
        """
        client, service = harmonized
        # Reproduce the old shape: the index is rebuilt by the run itself.
        client.execute("DROP INDEX image_meta_taxonomy_img_idx")
        client.execute("ALTER TABLE image_meta_taxonomy DROP COLUMN recorded_name")
        assert service.ensure() is True
        assert status_for(client, "img3")["recorded_name"] == "papilio_pamphilus"

    def test_a_new_schema_version_forces_a_rebuild(self, harmonized, monkeypatch):
        """An upgrade must not be mistaken for an up-to-date database."""
        import app.services.taxonomy_update as module

        _, service = harmonized
        # Unchanged inputs: without the version this would be skipped.
        assert service.ensure() is False
        monkeypatch.setattr(module, "STATUS_SCHEMA_VERSION", 99)
        assert service.ensure() is True


class TestTaxonomyValidationStats:
    """Family counts scoped to occurrences colharmonize resolved with confidence.

    Of the six OCCURRENCES, four are MATCHED (img1, img2, img3, img4) and all
    four resolve into Nymphalidae -- img3 as a synonym, img4 by cascading to
    the genus. The AMBIGUOUS and UNMATCHED rows (img6, img5) must not count.
    """

    @pytest.fixture
    def validation(self, harmonized):
        from app.services.taxonomy_update import TaxonomyValidationStats

        client, _ = harmonized
        service = TaxonomyValidationStats.__new__(TaxonomyValidationStats)
        service.status_table = "image_meta_taxonomy"
        service.db_client = client
        return service

    def test_counts_only_the_resolved_family(self, validation):
        assert validation.get_validated_family_count() == 1

    def test_excludes_ambiguous_and_unmatched_occurrences(self, validation):
        # Four MATCHED rows out of six total occurrences.
        assert validation.count_images_per_validated_family()["Nymphalidae"] == 4

    def test_missing_status_table_returns_none(self, memory_duckdb):
        from app.services.taxonomy_update import TaxonomyValidationStats

        service = TaxonomyValidationStats.__new__(TaxonomyValidationStats)
        service.status_table = "image_meta_taxonomy"
        service.db_client = memory_duckdb
        assert service.get_validated_family_count() is None
        assert service.count_images_per_validated_family() is None


class TestBatchLookup:
    """The one place a set of occurrences is mapped to its updated taxonomy."""

    @pytest.fixture
    def reader(self, harmonized):
        from app.services.taxonomy_update import OccurrenceTaxonomy

        client, _ = harmonized
        service = OccurrenceTaxonomy.__new__(OccurrenceTaxonomy)
        service.status_table = "image_meta_taxonomy"
        service.candidates_table = "col_taxonomy_candidates"
        service.db_client = client
        return service

    def test_returns_rows_keyed_by_image(self, reader):
        resolved = reader.get_for_images(["img1", "img3"])
        assert set(resolved) == {"img1", "img3"}
        assert resolved["img1"]["recorded_name"] == "coenonympha_pamphilus"

    def test_one_taxon_under_two_names_shares_an_identity(self, reader):
        """img3 is a synonym of img1's taxon; both must key the same."""
        resolved = reader.get_for_images(["img1", "img3"])
        assert resolved["img1"]["accepted_key"] == resolved["img3"]["accepted_key"]
        assert resolved["img1"]["accepted_key"]

    def test_unresolved_rows_are_returned_without_an_identity(self, reader):
        """Present, so a caller can tell 'no match' from 'not in the run'."""
        resolved = reader.get_for_images(["img5"])
        assert resolved["img5"]["update_status"] == "UNMATCHED"
        assert resolved["img5"]["accepted_key"] is None

    def test_unknown_images_are_absent(self, reader):
        assert reader.get_for_images(["img1", "nosuchimage"]).keys() == {"img1"}

    def test_no_images_is_not_a_query(self, reader):
        assert reader.get_for_images([]) == {}

    def test_accepted_keys_for_a_name_skips_the_unresolved(self, reader):
        """img5 is recorded but unmatched, so it contributes no identity."""
        assert reader.accepted_keys_for_species("nonexistent_taxon") == set()

    def test_accepted_keys_find_the_taxon_a_name_resolves_to(self, reader):
        """img1 and img3 are one taxon under two names, so both agree."""
        accepted = reader.accepted_keys_for_species("coenonympha_pamphilus")
        synonym = reader.accepted_keys_for_species("papilio_pamphilus")
        assert len(accepted) == 1
        assert accepted == synonym

    def test_accepted_keys_normalize_the_name(self, reader):
        """Callers pass a URL slug or a spaced name interchangeably."""
        assert reader.accepted_keys_for_species(
            "Coenonympha Pamphilus"
        ) == reader.accepted_keys_for_species("coenonympha_pamphilus")

    def test_accepted_keys_for_an_unknown_name_is_empty(self, reader):
        assert reader.accepted_keys_for_species("no_such_species") == set()


class TestAcceptedKey:
    """What counts as one taxon, for de-duplicating and for self-exclusion."""

    def test_identity_follows_the_displayed_name_not_the_usage_id(self):
        """Seen for real on the Junonia coenia page.

        `Junonia grisea` resolves to a CoL *subspecies* usage and
        `Junonia coenia` to the *species* usage — different ids whose binomial
        is identical. Keying on the id put a card labelled "Junonia coenia"
        into Junonia coenia's own list of similar species.
        """
        from app.services.taxonomy_update import accepted_key

        species = {"accepted_id": "6NHMZ", "display_accepted_name": "Junonia coenia"}
        subspecies = {"accepted_id": "Q6JT5", "display_accepted_name": "Junonia coenia"}
        assert accepted_key(species) == accepted_key(subspecies)

    def test_distinct_names_keep_distinct_identities(self):
        from app.services.taxonomy_update import accepted_key

        assert accepted_key({"display_accepted_name": "Junonia coenia"}) != accepted_key(
            {"display_accepted_name": "Junonia grisea"}
        )

    def test_falls_back_to_the_usage_id_without_a_name(self):
        from app.services.taxonomy_update import accepted_key

        assert accepted_key({"accepted_id": "6NHMZ", "display_accepted_name": None}) == "6NHMZ"

    def test_nothing_resolved_has_no_identity(self):
        from app.services.taxonomy_update import accepted_key

        assert accepted_key({"accepted_id": None, "display_accepted_name": ""}) is None

    def test_a_missing_run_is_probed_not_queried(self, memory_duckdb, monkeypatch):
        from app.services.taxonomy_update import OccurrenceTaxonomy

        service = OccurrenceTaxonomy.__new__(OccurrenceTaxonomy)
        service.status_table = "image_meta_taxonomy"
        service.candidates_table = "col_taxonomy_candidates"
        service.db_client = memory_duckdb
        service._status_present = None

        def fail(*args, **kwargs):
            raise AssertionError("queried a table that is not there")

        monkeypatch.setattr(memory_duckdb, "execute_prepared_to_pl", fail)
        assert service.get_for_images(["img1", "img2"]) == {}


def test_harmonizes_the_filtered_view(memory_duckdb, col_fixture_dir, tmp_path):
    """Excluded families never reach the per-occurrence status table."""
    from app.services.metadata import ImageMetaService

    seed_occurrences(memory_duckdb)
    memory_duckdb.execute_prepared(
        "INSERT INTO image_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "moth",
            "castnia_invaria",
            "Castniidae",
            None,
            None,
            None,
            None,
            "species",
            "accepted",
        ],
    )
    meta = ImageMetaService(memory_duckdb)
    meta.table = "image_meta"
    meta.source_table = "image_meta_source"
    meta.exclude_families = ["castniidae"]
    meta.apply_exclusions()

    service = build_service(memory_duckdb, col_fixture_dir, tmp_path)
    assert service.ensure() is True
    total, moths = memory_duckdb.execute(
        "SELECT count(*), count(*) FILTER (WHERE img_id = 'moth') "
        "FROM image_meta_taxonomy"
    ).fetchone()
    assert (total, moths) == (len(OCCURRENCES), 0)
    assert status_for(memory_duckdb, "img1")["update_status"] == "MATCHED"
