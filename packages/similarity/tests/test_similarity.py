from __future__ import annotations

from pathlib import Path

import duckdb
import lancedb
import numpy as np
import polars as pl
import pyarrow as pa
import pytest
from typer.testing import CliRunner

from similarity.cli import app
from similarity.compute import build_results

WIDTH = 8
# Species and the direction of their embeddings: `danaus_a` sits closer to
# `danaus_b` than to `papilio_c`.
SPECIES = {
    "Danaus a": [1.0, 0.0],
    "Danaus b": [0.9, 0.3],
    "Papilio c": [0.0, 1.0],
}


def _collection(tmp_path: Path) -> tuple[Path, Path]:
    rng = np.random.default_rng(3)
    meta, ids, vectors = [], [], []
    for name, direction in SPECIES.items():
        base = np.zeros(WIDTH)
        base[:2] = direction
        for side in ("Dorsal", "ventral"):
            for number in range(3):
                img_id = f"{name.replace(' ', '_').lower()}_{side.lower()}_{number}"
                meta.append((img_id, name, side))
                ids.append(img_id)
                vectors.append(base + 0.01 * rng.normal(size=WIDTH))
    # An image with an embedding but no metadata row (an excluded family).
    ids.append("moth")
    vectors.append(np.eye(WIDTH)[0])

    database = tmp_path / "biocosmos.duckdb"
    connection = duckdb.connect(str(database))
    connection.execute(
        "CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR, class_dv VARCHAR)"
    )
    connection.executemany("INSERT INTO image_meta VALUES (?, ?, ?)", meta)
    connection.close()

    lance_dir = tmp_path / "biocosmos.lance"
    matrix = np.asarray(vectors, dtype=np.float32)
    arrow = pa.table(
        {
            "img_id": pa.array(ids, pa.string()),
            "unicom_embeddings": pa.FixedSizeListArray.from_arrays(
                pa.array(matrix.ravel(), pa.float32()), WIDTH
            ),
        }
    )
    lancedb.connect(str(lance_dir)).create_table("images", arrow)
    return database, lance_dir


def _run(database: Path, lance_dir: Path, *extra: str):
    result = CliRunner().invoke(
        app,
        ["run", "--db", str(database), "--lance-dir", str(lance_dir), "--lance-table", "images"]
        + list(extra),
    )
    assert result.exit_code == 0, result.output
    return result


def _rows(database: Path, query: str) -> list[tuple]:
    connection = duckdb.connect(str(database), read_only=True)
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


@pytest.fixture
def collection(tmp_path: Path) -> tuple[Path, Path]:
    return _collection(tmp_path)


def test_ranks_the_nearest_other_species(collection):
    database, lance_dir = collection
    _run(database, lance_dir)
    rows = _rows(
        database,
        "SELECT side, similar_species, rank FROM species_similarity "
        "WHERE species = 'danaus_a' ORDER BY side, rank",
    )
    assert rows == [
        ("dorsal", "danaus_b", 1),
        ("dorsal", "papilio_c", 2),
        ("ventral", "danaus_b", 1),
        ("ventral", "papilio_c", 2),
    ]
    # Every species on both sides, never itself, never the unlabeled image.
    assert _rows(database, "SELECT count(*) FROM species_similarity") == [(12,)]
    assert _rows(
        database,
        "SELECT count(*) FROM species_similarity WHERE species = similar_species "
        "OR img_id = 'moth'",
    ) == [(0,)]


def test_rerun_replaces_rather_than_appends(collection):
    database, lance_dir = collection
    _run(database, lance_dir)
    _run(database, lance_dir)
    assert _rows(database, "SELECT count(*) FROM species_similarity") == [(12,)]


def test_single_species_replaces_only_its_rows(collection):
    database, lance_dir = collection
    _run(database, lance_dir, "--limit", "2")
    _run(database, lance_dir, "--species", "Danaus A", "--limit", "1")
    counts = dict(
        _rows(database, "SELECT species, count(*) FROM species_similarity GROUP BY species")
    )
    assert counts == {"danaus_a": 2, "danaus_b": 4, "papilio_c": 4}


def test_missing_database_fails_cleanly(tmp_path):
    result = CliRunner().invoke(
        app, ["run", "--db", str(tmp_path / "none.duckdb"), "--lance-dir", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "DuckDB file not found" in result.output


def test_build_results_skips_self_and_duplicates():
    meta = pl.DataFrame(
        {"img_id": ["a1", "a2", "b1", "b2", "c1"], "species": ["a", "a", "b", "b", "c"]}
    )
    img_ids = np.array(["a1", "a2", "b1", "b2", "c1"], dtype=object)
    top_indices = np.array([[0, 1, 2, 3, 4]])
    top_distances = np.array([[0.0, 0.1, 0.2, 0.3, 0.4]], dtype=np.float32)
    frame = build_results([("a", "dorsal")], top_indices, top_distances, img_ids, meta, 5)
    assert frame["similar_species"].to_list() == ["b", "c"]
    assert frame["img_id"].to_list() == ["b1", "c1"]
    assert frame["rank"].to_list() == [1, 2]
