from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


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
