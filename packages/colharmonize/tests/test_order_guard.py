"""Matches placed in another order than the recorded one are rejected."""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from colharmonize.index import ReferenceIndex
from colharmonize.models import ColumnMappings, MatchingConfig
from colharmonize.pipeline import MatchPipeline
from colharmonize.sources import ColSource, TaxonOccurrenceSource

REFERENCE = [
    # The butterfly moved under a bug genus, as CoL 2026-10-16 did with Capys.
    ("B1", "Capys alpheus", "species", "provisionally accepted", "", "Berytidae", "Hemiptera"),
    ("B2", "Capys", "genus", "accepted", "", "Berytidae", "Hemiptera"),
    # A homonym: the species-rank hit is in another order, the genus is not.
    ("H1", "Homonymus alpha", "species", "accepted", "", "Bugidae", "Hemiptera"),
    ("H2", "Homonymus", "genus", "accepted", "", "Lycaenidae", "Lepidoptera"),
    ("P1", "Papilio machaon", "species", "accepted", "", "Papilionidae", "Lepidoptera"),
    ("N1", "Nullus orderless", "species", "accepted", "", "Nullidae", ""),
]
INPUTS = [
    ("Capys alpheus", "Lycaenidae", "Lepidoptera"),
    ("Homonymus alpha", "Lycaenidae", "Lepidoptera"),
    ("Papilio machaon", "Papilionidae", "Lepidoptera"),
    ("Nullus orderless", "Nullidae", "Lepidoptera"),
    ("Capys alpheus", "Berytidae", None),
]


def run(tmp_path: Path, matching: MatchingConfig | None = None) -> list[tuple]:
    reference = tmp_path / "NameUsage.tsv"

    with reference.open("w") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["ID", "scientificName", "rank", "status", "parentID", "family", "order"])
        writer.writerows(REFERENCE)

    database = tmp_path / "input.duckdb"

    with duckdb.connect(str(database)) as connection:
        connection.execute(
            'CREATE TABLE occurrence (scientificName VARCHAR, family VARCHAR, "order" VARCHAR)'
        )
        connection.executemany("INSERT INTO occurrence VALUES (?, ?, ?)", INPUTS)

    source = TaxonOccurrenceSource(database, "occurrence")

    with source.connect() as connection:
        columns, _ = source.resolve_columns(
            source.columns(connection), ColumnMappings(), strict=True
        )

    index = ReferenceIndex(tmp_path / "cache").ensure(ColSource(reference))
    connection = duckdb.connect(":memory:")
    MatchPipeline(connection, source, columns, index.path, matching or MatchingConfig()).run()

    try:
        return connection.execute(
            """
            SELECT original_scientific_name, original_order, match_method, accepted_id,
                reason_code
            FROM taxonomy_matches
            ORDER BY original_scientific_name, original_order NULLS LAST
            """
        ).fetchall()
    finally:
        connection.close()


def test_matches_outside_the_recorded_order_are_rejected(tmp_path):
    rows = {(name, order): rest for name, order, *rest in run(tmp_path)}

    # Every candidate is a bug: unmatched, with the reason recorded.
    assert rows[("Capys alpheus", "Lepidoptera")] == ["UNMATCHED", None, "ORDER_MISMATCH"]
    # The species hit is rejected, so the genus stage gets its turn.
    assert rows[("Homonymus alpha", "Lepidoptera")] == ["GENUS_EXACT_ACCEPTED", "H2", None]
    assert rows[("Papilio machaon", "Lepidoptera")] == ["EXACT_ACCEPTED", "P1", None]
    # A missing order on either side cannot disagree.
    assert rows[("Nullus orderless", "Lepidoptera")] == ["EXACT_ACCEPTED", "N1", None]
    assert rows[("Capys alpheus", None)] == ["EXACT_ACCEPTED", "B1", None]


def test_default_order_covers_inputs_without_one(tmp_path):
    rows = {
        (name, order): rest
        for name, order, *rest in run(tmp_path, MatchingConfig(default_order="Lepidoptera"))
    }

    assert rows[("Capys alpheus", None)] == ["UNMATCHED", None, "ORDER_MISMATCH"]
    assert rows[("Papilio machaon", "Lepidoptera")] == ["EXACT_ACCEPTED", "P1", None]
