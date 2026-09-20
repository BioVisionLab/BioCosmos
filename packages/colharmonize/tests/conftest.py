from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def col_tsv(tmp_path: Path) -> Path:
    path = tmp_path / "NameUsage.tsv"
    rows = [
        (
            "A1",
            "Panthera leo",
            "Linnaeus, 1758",
            "species",
            "accepted",
            "",
            "Panthera",
            "leo",
            "Felidae",
        ),
        ("S1", "Leo leo", "Linnaeus, 1758", "species", "synonym", "A1", "Leo", "leo", "Felidae"),
        (
            "A2",
            "Panthera tigris",
            "Linnaeus, 1758",
            "species",
            "accepted",
            "",
            "Panthera",
            "tigris",
            "Felidae",
        ),
        (
            "A3",
            "Pseudopanthera leo",
            "Smith, 1900",
            "species",
            "accepted",
            "",
            "Pseudopanthera",
            "leo",
            "Felidae",
        ),
        ("A4", "Nova alpha", "Author, 1901", "species", "accepted", "", "Nova", "alpha", "Novidae"),
        ("A5", "Genus beta", "One, 1902", "species", "accepted", "", "Genus", "beta", "Testidae"),
        ("A6", "Tenus beta", "Two, 1903", "species", "accepted", "", "Tenus", "beta", "Testidae"),
        ("G1", "Panthera", "", "genus", "accepted", "", "Panthera", "", "Felidae"),
    ]
    header = (
        "ID\tscientificName\tauthorship\trank\tstatus\tparentID\t"
        "genericName\tspecificEpithet\tfamily\n"
    )
    path.write_text(header + "".join("\t".join(row) + "\n" for row in rows), encoding="utf-8")
    return path


@pytest.fixture
def occurrence_db(tmp_path: Path) -> Path:
    path = tmp_path / "occurrence.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE occurrence(
            occurrenceID VARCHAR,
            scientificName VARCHAR,
            species VARCHAR,
            family VARCHAR,
            taxonRank VARCHAR,
            scientificNameAuthorship VARCHAR
        )
        """
    )
    rows = [
        ("1", "Panthera leo", "Panthera leo", "Felidae", "species", None),
        ("2", "Panthera leo", "Panthera leo", "Felidae", "species", None),
        ("3", "Leo leo", "Leo leo", "Felidae", "species", None),
        ("4", "Panthera leo Linnaeus", "Panthera leo Linnaeus", "Felidae", "species", None),
        ("5", "Old alpha", "Old alpha", "Novidae", "species", None),
        ("6", "Panthra tigris", "Panthra tigris", "Felidae", "species", None),
        ("7", "Panthera tigrus", "Panthera tigrus", "Felidae", "species", None),
        ("8", "Panthra tigrus", "Panthra tigrus", "Felidae", "species", None),
        ("9", "Xenus beta", "Xenus beta", "Testidae", "species", None),
        ("10", "Nothing nowhere", "Nothing nowhere", "Missingidae", "species", None),
        ("11", "Panthera", "Panthera", "Felidae", "genus", None),
    ]
    connection.executemany("INSERT INTO occurrence VALUES (?, ?, ?, ?, ?, ?)", rows)
    connection.close()
    return path
