"""Tests for the collection-wide statistics ImageMetaStats computes.

Institution counts and the source-db bucketing both depend on how image_meta
and gbif_meta relate, so they are tested against a real in-memory DuckDB
rather than mocked out.
"""

import pytest

from app.services.metadata import ImageMetaStats

IMAGE_META_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, uuid VARCHAR, family VARCHAR, species VARCHAR,
        source_db VARCHAR
    )
"""

GBIF_META_DDL = """
    CREATE TABLE gbif_meta (
        "gbifID" BIGINT, "occurrenceID" VARCHAR, "institutionCode" VARCHAR
    )
"""


def seed(client, images, gbif_rows) -> None:
    client.execute(IMAGE_META_DDL)
    for row in images:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, ?, ?, ?)", list(row)
        )
    client.execute(GBIF_META_DDL)
    for row in gbif_rows:
        client.execute_prepared("INSERT INTO gbif_meta VALUES (?, ?, ?)", list(row))


@pytest.fixture
def stats(memory_duckdb):
    seed(
        memory_duckdb,
        images=[
            ("img1", "occ-1", "nymphalidae", "danaus_plexippus", "gbif"),
            ("img2", "occ-2", "nymphalidae", "danaus_plexippus", "gbif"),
            # No GBIF record for this occurrence at all.
            ("img3", "occ-missing", "pieridae", "colias_eurytheme", "scanbugs"),
            # A GBIF record with no institution code recorded.
            ("img4", "occ-4", "pieridae", "colias_eurytheme", "gbif"),
            # Published to two aggregators at once.
            ("img5", "occ-5", "papilionidae", "papilio_glaucus", "gbif/scanbugs"),
        ],
        gbif_rows=[
            (1, "occ-1", "NHMUK"),
            (2, "occ-2", "NHMUK"),
            (3, "occ-4", None),
            (4, "occ-5", "MCZ"),
        ],
    )
    return ImageMetaStats(duckdb=memory_duckdb)


class TestSourceDbCount:
    def test_canonical_sources_are_kept_as_is(self, stats):
        counts = stats.get_source_db_count()
        assert counts["gbif"] == 3
        assert counts["scanbugs"] == 1

    def test_multi_aggregator_records_are_bucketed_as_multiple(self, stats):
        """'gbif/scanbugs' is a real recorded value, not an unknown source.

        Calling it 'other' would suggest a fourth aggregator that does not
        exist; every non-canonical value in this table is a combination of
        the three canonical ones.
        """
        counts = stats.get_source_db_count()
        assert counts["multiple"] == 1
        assert "other" not in counts


class TestInstitutionCounts:
    def test_counts_by_institution_code(self, stats):
        counts = stats.get_institution_counts()
        assert counts["NHMUK"] == 2

    def test_records_with_no_gbif_match_are_unknown(self, stats):
        counts = stats.get_institution_counts()
        assert counts["Unknown"] >= 1

    def test_records_with_a_blank_institution_code_are_unknown(self, stats):
        """occ-4 has a GBIF record, but institutionCode itself is null."""
        counts = stats.get_institution_counts()
        # img3 (no GBIF record) and img4 (null institutionCode) both fold in.
        assert counts["Unknown"] == 2

    def test_every_image_is_accounted_for(self, stats):
        counts = stats.get_institution_counts()
        assert sum(counts.values()) == 5

    def test_missing_gbif_table_returns_none(self, memory_duckdb):
        memory_duckdb.execute(IMAGE_META_DDL)
        stats = ImageMetaStats(duckdb=memory_duckdb)
        assert stats.get_institution_counts() is None
