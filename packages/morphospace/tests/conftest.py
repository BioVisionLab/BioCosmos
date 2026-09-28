"""A tiny synthetic collection: DuckDB labels plus a LanceDB embedding table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import lancedb
import numpy as np
import pyarrow as pa
import pytest

WIDTH = 16

# genus -> species epithets. `solo` has too few species to be a genus scope.
GENERA = {
    "Alpha": ["one", "two", "three", "four", "five", "six"],
    "Beta": ["one", "two", "three"],
    "Solo": ["one"],
}
FAMILY = "Testidae"
IMAGES_PER_SIDE = 4


@dataclass(frozen=True)
class Collection:
    database: Path
    lance_dir: Path
    table: str


def _unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def build_collection(tmp_path: Path, *, identical_sides: bool = False) -> Collection:
    rng = np.random.default_rng(7)
    meta, taxonomy, ids, vectors = [], [], [], []
    for genus, epithets in GENERA.items():
        genus_shift = rng.normal(size=WIDTH)
        for epithet in epithets:
            dorsal = _unit(genus_shift + rng.normal(size=WIDTH))
            ventral = dorsal if identical_sides else _unit(genus_shift + rng.normal(size=WIDTH))
            name = f"{genus} {epithet}"
            for side, centre in (("Dorsal", dorsal), ("ventral", ventral)):
                for number in range(IMAGES_PER_SIDE):
                    img_id = f"{genus}_{epithet}_{side}_{number}".lower()
                    meta.append((img_id, name.lower().replace(" ", "_"), side))
                    taxonomy.append((img_id, "MATCHED", name, name, FAMILY))
                    ids.append(img_id)
                    vectors.append(_unit(centre + 0.05 * rng.normal(size=WIDTH)))
    # An image resolved only to genus rank, and one that never matched: both ignored.
    meta += [("genus_only", "alpha", "dorsal"), ("unmatched", "x_y", "dorsal")]
    taxonomy += [
        ("genus_only", "MATCHED", "Alpha", None, FAMILY),
        ("unmatched", "UNMATCHED", None, None, None),
    ]
    ids += ["genus_only", "unmatched"]
    vectors += [_unit(rng.normal(size=WIDTH)), _unit(rng.normal(size=WIDTH))]

    database = tmp_path / "biocosmos.duckdb"
    connection = duckdb.connect(str(database))
    connection.execute(
        "CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR, class_dv VARCHAR)"
    )
    connection.executemany("INSERT INTO image_meta VALUES (?, ?, ?)", meta)
    connection.execute(
        "CREATE TABLE image_meta_taxonomy (img_id VARCHAR, update_status VARCHAR, "
        "accepted_name VARCHAR, accepted_species_name VARCHAR, accepted_family VARCHAR)"
    )
    connection.executemany("INSERT INTO image_meta_taxonomy VALUES (?, ?, ?, ?, ?)", taxonomy)
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
    return Collection(database, lance_dir, "images")


@pytest.fixture
def collection(tmp_path: Path) -> Collection:
    return build_collection(tmp_path)
