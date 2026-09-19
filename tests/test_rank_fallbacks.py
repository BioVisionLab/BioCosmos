from __future__ import annotations

import csv

import duckdb
import pytest

from colharmonize.index import INDEX_SCHEMA_VERSION, ReferenceIndex
from colharmonize.models import ColumnMappings, MatchingConfig
from colharmonize.pipeline import MatchPipeline
from colharmonize.sources import ColSource, OccurrenceSource
from colharmonize.summary import SummaryService


def run_fixture(tmp_path, references, inputs, *, top_k=5):
    reference = tmp_path / "reference.tsv"
    with reference.open("w") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(
            [
                "ID",
                "scientificName",
                "rank",
                "status",
                "parentID",
                "family",
                "infraspecificEpithet",
                "authorship",
            ]
        )
        writer.writerows(references)
    database = tmp_path / "input.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("""CREATE TABLE occurrence (
            scientificName VARCHAR, taxonRank VARCHAR, family VARCHAR,
            infraspecificEpithet VARCHAR, scientificNameAuthorship VARCHAR)""")
        connection.executemany("INSERT INTO occurrence VALUES (?, ?, ?, ?, ?)", inputs)
    source = OccurrenceSource(database, "occurrence")
    with source.connect() as connection:
        columns, _ = source.resolve_columns(
            source.columns(connection), ColumnMappings(), strict=True
        )
    assert columns["infraspecific_epithet"] == "infraspecificEpithet"
    index = ReferenceIndex(tmp_path / "cache").ensure(ColSource(reference))
    connection = duckdb.connect(str(tmp_path / "output.duckdb"))
    MatchPipeline(connection, source, columns, index.path, MatchingConfig(top_k=top_k)).run()
    return connection, index


def ref(id, name, rank="subspecies", family="Felidae", status="accepted", parent="", infra=""):
    return (id, name, rank, status, parent, family, infra, "")


def test_rank_cascade_and_parsing(tmp_path):
    references = [
        ref("S", "Panthera leo", "species"),
        ref("L", "Lynx lynx", "species"),
        ref("U", "Panthera pardus fusca"),
        ref("V", "Panthera leo persica"),
        ref("US", "Felis pardus fusca", status="synonym", parent="U"),
        ref("G", "Panthera", "genus"),
        ref("GS", "Leo", "genus", status="synonym", parent="G"),
        ref("G2", "Panthera", "genus", family="Otheridae"),
        ref("A", "Alpha animal minor", family="Testidae"),
        ref("B", "Beta animal minor", family="Testidae"),
        ref("GX", "Xenus", "genus", family="Testidae"),
        ref("P", "Alpha beta", "species", family="Testidae"),
        ref("Q", "Beta beta", "species", family="Testidae"),
        ref("Qsub", "Xenus animal beta", family="Testidae"),
    ]
    cases = [
        ("Panthera leo", "species", "Felidae", None, None, "S", "EXACT_ACCEPTED"),
        ("Panthera leo persica", "species", "Felidae", None, None, "S", "EXACT_CANONICAL"),
        ("Panthera fusca", "species", "Felidae", None, None, "U", "SUBSPECIES_EXACT_CANONICAL"),
        (
            "Panthera pardus fusca",
            "subspecies",
            "Felidae",
            None,
            None,
            "U",
            "SUBSPECIES_EXACT_ACCEPTED",
        ),
        (
            "Panthera pardus subsp. fusca",
            "subspecies",
            "Felidae",
            None,
            None,
            "U",
            "SUBSPECIES_EXACT_CANONICAL",
        ),
        (
            "Panthera_pardus_ssp._fusca",
            "subspecies",
            "Felidae",
            None,
            None,
            "U",
            "SUBSPECIES_EXACT_CANONICAL",
        ),
        (
            "Panthera pardus Smith",
            "subspecies",
            "Felidae",
            "fusca",
            None,
            "U",
            "SUBSPECIES_EXACT_CANONICAL",
        ),
        ("Felis fusca", "species", "Felidae", None, None, "U", "SUBSPECIES_EXACT_SYNONYM"),
        ("Panthera fuska", "species", "Felidae", None, None, "U", "SUBSPECIES_SPELLING_EPITHET"),
        ("Panthra fuska", "species", "Felidae", None, None, "U", "SUBSPECIES_FUZZY_TYPO"),
        ("Old fusca", "species", "Felidae", None, None, "U", "SUBSPECIES_UNIQUE_FAMILY_EPITHET"),
        ("Panthera missing", "species", "Felidae", None, None, "G", "GENUS_EXACT_ACCEPTED"),
        ("Leo missing", "species", "Felidae", None, None, "G", "GENUS_EXACT_SYNONYM"),
        ("Panthera", "genus", "Felidae", None, None, "G", "GENUS_EXACT_ACCEPTED"),
        ("Panthera", "genus", None, None, None, "G", "AMBIGUOUS"),
        ("Panthera", "genus", "Missingidae", None, None, None, "UNMATCHED"),
        ("Panthra missing", "species", "Felidae", None, None, None, "UNMATCHED"),
        ("Unknown missing", "species", None, None, None, None, "UNMATCHED"),
        ("Panthera", "species", None, None, None, None, "UNMATCHED"),
        ("Panthera pardus Smith", "subspecies", "Felidae", None, None, None, "UNMATCHED"),
        ("Panthera pardus smith", "subspecies", "Felidae", None, "smith", None, "UNMATCHED"),
        ("Panthera pardus", "variety", "Felidae", None, None, None, "UNMATCHED"),
        ("Panthera ???", "species", "Felidae", None, None, None, "UNMATCHED"),
        ("Xenus minor", "species", "Testidae", None, None, "B", "AMBIGUOUS"),
        ("Xenus beta", "species", "Testidae", None, None, "Q", "AMBIGUOUS"),
    ]
    cases.extend(
        [
            (
                "Panthera leo persica",
                "subspecies",
                "Felidae",
                None,
                None,
                "V",
                "SUBSPECIES_EXACT_ACCEPTED",
            ),
            (
                "Panthera leo fusca",
                "subspecies",
                "Felidae",
                "persica",
                None,
                "V",
                "SUBSPECIES_EXACT_CANONICAL",
            ),
            (
                "Panthera pardus fusca",
                "subspecies",
                "Felidae",
                "missing",
                None,
                "G",
                "GENUS_EXACT_ACCEPTED",
            ),
            ("Lynx unknown", "species", None, None, None, None, "UNMATCHED"),
        ]
    )
    connection, _ = run_fixture(tmp_path, references, [row[:5] for row in cases])
    try:
        for name, rank, family, infra, author, accepted, method in cases:
            result = connection.execute(
                """SELECT accepted_id, match_method, accepted_rank
                FROM taxonomy_matches WHERE original_scientific_name = ?
                AND original_taxon_rank = ? AND original_family IS NOT DISTINCT FROM ?
                AND original_infraspecific_epithet IS NOT DISTINCT FROM ?
                AND original_authorship IS NOT DISTINCT FROM ?""",
                [name, rank, family, infra, author],
            ).fetchone()
            assert result is not None
            assert result[:2] == (accepted, method), (name, result)
            if method.startswith("SUBSPECIES"):
                assert result[2] == "subspecies"
            if method.startswith("GENUS"):
                assert result[2] == "genus"
        assert (
            connection.execute("""SELECT DISTINCT accepted_rank FROM taxonomy_candidates
            WHERE input_taxon_key IN (SELECT input_taxon_key FROM taxonomy_matches
                                     WHERE original_scientific_name = 'Xenus beta')""").fetchall()
            == [("species",)]
        )
    finally:
        connection.close()


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 6])
def test_alternatives_before_top_k(tmp_path, count):
    names = ["Alpha beta", "Bravo beta", "Delta beta", "Gamma beta", "Omega beta", "Zebra beta"]
    references = [
        ref(str(i), name, "species", family="Testidae") for i, name in enumerate(names[:count])
    ]
    references += [ref("G", "Unrelated", "genus")]
    if count:
        references += [
            ref("syn", names[0], "species", family="Testidae", status="synonym", parent="0")
        ]
    connection, _ = run_fixture(
        tmp_path, references, [("Xenus beta", "species", "Testidae", None, None)], top_k=1
    )
    try:
        all_names = [
            row[0]
            for row in connection.execute(
                "SELECT accepted_name FROM ranked_candidates ORDER BY candidate_rank"
            ).fetchall()
        ]
        alternatives = connection.execute(
            "SELECT alternative_matches FROM taxonomy_matches"
        ).fetchone()[0]
        assert alternatives == ("; ".join(all_names[1:4]) or None)
        assert len(all_names) == count
        assert connection.execute("SELECT count(*) FROM taxonomy_candidates").fetchone()[0] == min(
            1, count
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('taxonomy_matches')").fetchall()
        }
        assert "runner_up_name" not in columns and "runner_up_score" not in columns
    finally:
        connection.close()
    path = SummaryService().export_csv(tmp_path / "output.duckdb", tmp_path, force=False)
    with path.open() as stream:
        row = next(csv.DictReader(stream))
    assert row["alternative_matches"] == (alternatives or "")
    assert "accepted_rank" in row


def test_index_cache_and_structured_epithet(tmp_path):
    references = [ref("U", "Panthera pardus Smith", infra="fusca"), ref("G", "Panthera", "genus")]
    connection, index = run_fixture(
        tmp_path, references, [("Panthera fusca", "species", None, None, None)]
    )
    assert connection.execute("SELECT accepted_id FROM taxonomy_matches").fetchone()[0] == "U"
    connection.close()
    assert INDEX_SCHEMA_VERSION == 2
    assert index.path.name == "reference-v2.duckdb"
    manager = ReferenceIndex(tmp_path / "cache")
    source = ColSource(tmp_path / "reference.tsv")
    assert manager.ensure(source).reused
    legacy = index.path.with_name("reference-v1.duckdb")
    index.path.rename(legacy)
    rebuilt = manager.ensure(source)
    assert not rebuilt.reused and rebuilt.path.name == "reference-v2.duckdb"
    assert legacy.is_file()
    with duckdb.connect(str(index.path), read_only=True) as connection:
        assert (
            connection.execute(
                "SELECT canonical_key FROM accepted_taxa WHERE accepted_id = 'U'"
            ).fetchone()[0]
            == "panthera pardus fusca"
        )


def test_legacy_summary(tmp_path):
    path = tmp_path / "legacy.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("""CREATE TABLE taxonomy_matches AS SELECT
            'key' AS input_taxon_key, 'Old name' AS original_scientific_name,
            'Family' AS original_family, 'New name' AS accepted_name, 'id' AS accepted_id,
            'EXACT_ACCEPTED' AS match_method, 7000 AS match_score, 'MATCHED' AS update_status,
            2 AS candidate_count, 'Other name' AS runner_up_name, 1000 AS score_margin""")
    result = SummaryService().export_csv(path, tmp_path, force=False)
    with result.open() as stream:
        row = next(csv.DictReader(stream))
    assert row["alternative_matches"] == "Other name"
    assert row["accepted_rank"] == ""
