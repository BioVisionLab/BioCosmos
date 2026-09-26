"""The LanceDB layout migration, run against a real on-disk table.

The table mirrors the production collection's original layout: image bytes in
the table, no `img_path`, and one small fragment per ingest batch.
"""

from unittest.mock import MagicMock

import lancedb
import numpy as np
import pyarrow as pa
import pytest
from lancedb.index import IvfFlat, IvfHnswPq

from app.database.lance import LanceDB
from app.database.lance_migration import MigrationError, _retrain, migrate

DIMS = 8


def _batch(ids):
    n = len(ids)
    vectors = np.random.default_rng(0).random(n * DIMS, dtype=np.float32)
    return pa.table(
        {
            "img_id": pa.array(ids, pa.string()),
            "img_bytes": pa.array([b"\x00"] * n, pa.binary()),
            "file_format": pa.array(["webp"] * n),
            "original_size": pa.array([True] * n),
            "unicom_embeddings": pa.FixedSizeListArray.from_arrays(
                pa.array(vectors), DIMS
            ),
        }
    )


@pytest.fixture
def legacy_table(tmp_path):
    db = lancedb.connect(str(tmp_path / "biocosmos.lance"))
    table = db.create_table("images", _batch(["a", "b"]))
    table.add(_batch(["c", "d"]))
    table.add(_batch(["e'f"]))
    return table


@pytest.fixture
def images_on_disk(tmp_path, legacy_table):
    processed = tmp_path / "webp"
    processed.mkdir()
    for img_id in ["a", "b", "c", "d", "e'f"]:
        (processed / f"{img_id}.webp").write_bytes(b"")
    return str(processed)


def _run(table, processed_dir, **kwargs):
    return migrate(table, processed_dir=processed_dir, image_format="webp", **kwargs)


class TestMigrate:
    def test_a_dry_run_reports_without_changing_anything(self, legacy_table):
        version = legacy_table.version
        report = _run(legacy_table, "static/webp")

        assert not report.applied
        assert report.start_version == version
        assert any("img_path" in s for s in report.steps)
        assert any("compact" in s for s in report.steps)
        assert any("BTREE" in s for s in report.steps)
        assert legacy_table.version == version
        assert "img_path" not in legacy_table.schema.names

    def test_apply_adds_the_path_the_image_routes_read(self, legacy_table):
        _run(legacy_table, "static/webp", apply=True)

        rows = legacy_table.search().select(["img_id", "img_path"]).to_list()
        paths = {r["img_id"]: r["img_path"] for r in rows}
        assert paths["a"] == "static/webp/a.webp"
        # A quote in an ID survives the SQL expression.
        assert paths["e'f"] == "static/webp/e'f.webp"
        assert legacy_table.stats()["fragment_stats"]["num_fragments"] == 1
        assert legacy_table.uses_v2_manifest_paths()
        assert any("img_id" in index.columns for index in legacy_table.list_indices())

    def test_moves_v1_manifests_to_v2_paths(self, tmp_path):
        """The production table predates v2 paths; new tables start with them."""
        db = lancedb.connect(str(tmp_path / "v1.lance"))
        # `enable_v2_manifest_paths=False` is mis-passed by lancedb 0.39, so the
        # option goes in as a storage option instead.
        table = db.create_table(
            "images",
            _batch(["a"]),
            storage_options={"new_table_enable_v2_manifest_paths": "false"},
        )
        assert not table.uses_v2_manifest_paths()

        _run(table, "static/webp", apply=True)

        assert table.uses_v2_manifest_paths()
        assert table.count_rows() == 1

    def test_a_second_run_has_nothing_to_do(self, legacy_table):
        _run(legacy_table, "static/webp", apply=True)
        assert _run(legacy_table, "static/webp").steps == []

    def test_legacy_columns_stay_unless_asked(self, legacy_table):
        _run(legacy_table, "static/webp", apply=True)
        assert "img_bytes" in legacy_table.schema.names

    def test_legacy_columns_are_not_dropped_while_images_are_missing(
        self, legacy_table, images_on_disk, tmp_path
    ):
        (tmp_path / "webp" / "c.webp").unlink()
        with pytest.raises(MigrationError, match="c"):
            _run(legacy_table, images_on_disk, apply=True, drop_legacy_columns=True)
        assert "img_bytes" in legacy_table.schema.names
        assert "img_path" not in legacy_table.schema.names

    def test_legacy_columns_drop_once_every_image_is_on_disk(
        self, legacy_table, images_on_disk
    ):
        _run(legacy_table, images_on_disk, apply=True, drop_legacy_columns=True)

        names = legacy_table.schema.names
        assert not {"img_bytes", "file_format", "original_size"} & set(names)
        assert legacy_table.count_rows() == 5

    def test_the_run_can_be_undone(self, legacy_table, images_on_disk):
        report = _run(
            legacy_table, images_on_disk, apply=True, drop_legacy_columns=True
        )
        legacy_table.restore(report.start_version)
        assert "img_bytes" in legacy_table.schema.names


class TestRetrain:
    def test_keeps_the_index_type_and_settings(self):
        table = MagicMock()
        table.count_rows.return_value = 640_000
        table.schema.field.return_value.type.list_size = 768
        index = MagicMock(
            index_type="IvfHnswPq",
            index_details={
                "metric_type": "COSINE",
                "hnsw": {"max_connections": 20, "construction_ef": 300},
                "compression": {"type": "pq", "num_bits": 8, "num_sub_vectors": 64},
            },
        )
        index.name = "unicom_embeddings_idx"

        _retrain(table, index, "unicom_embeddings", "IvfHnswPq")

        (column,) = table.create_index.call_args.args
        kwargs = table.create_index.call_args.kwargs
        config = kwargs["config"]
        assert column == "unicom_embeddings"
        assert isinstance(config, IvfHnswPq)
        assert config.distance_type == "cosine"
        assert config.num_sub_vectors == 64
        assert config.num_partitions == 800
        assert (config.m, config.ef_construction) == (20, 300)
        assert kwargs["replace"] is True
        assert kwargs["name"] == "unicom_embeddings_idx"

    def test_configured_type_replaces_the_existing_type(self):
        table = MagicMock()
        table.count_rows.return_value = 640_000
        table.schema.field.return_value.type.list_size = 768
        index = MagicMock(
            index_type="IvfHnswPq", index_details={"metric_type": "COSINE"}
        )
        index.name = "unicom_embeddings_idx"

        _retrain(table, index, "unicom_embeddings", "IvfFlat")

        config = table.create_index.call_args.kwargs["config"]
        assert isinstance(config, IvfFlat)
        assert config.distance_type == "cosine"
        assert config.num_partitions == 800

    def test_a_dry_run_lists_vector_indexes_to_retrain(self):
        table = MagicMock()
        table.version = 7
        table.schema.names = ["img_id", "img_path", "unicom_embeddings"]
        table.uses_v2_manifest_paths.return_value = True
        table.stats.return_value = {"fragment_stats": {"num_small_fragments": 1}}
        vector = MagicMock(index_type="IvfHnswPq", columns=["unicom_embeddings"])
        vector.name = "unicom_embeddings_idx"
        scalar = MagicMock(index_type="BTree", columns=["img_id"])
        table.list_indices.return_value = [vector, scalar]

        report = _run(table, "static/webp", reindex=True)

        assert report.steps == [
            "rebuild unicom_embeddings_idx on 'unicom_embeddings' as IvfPq"
        ]
        table.create_index.assert_not_called()


class TestLanceDBWrapper:
    def _wrapper(self, tmp_path):
        db = LanceDB.__new__(LanceDB)
        db.db = lancedb.connect(str(tmp_path / "biocosmos.lance"))
        return db

    def test_reports_a_legacy_layout(self, tmp_path, legacy_table):
        problems = self._wrapper(tmp_path).schema_problems("images")
        assert "missing column 'img_path'" in problems
        assert "legacy column 'img_bytes'" in problems

    def test_a_migrated_layout_has_no_problems(self, tmp_path, legacy_table):
        _run(legacy_table, "static/webp", apply=True, drop_legacy_columns=False)
        legacy_table.drop_columns(["img_bytes", "file_format", "original_size"])
        legacy_table.add_columns(
            [pa.field("clip_embeddings", pa.list_(pa.float32(), 4))]
        )
        assert self._wrapper(tmp_path).schema_problems("images") == []

    def test_a_missing_collection_has_no_problems(self, tmp_path):
        assert self._wrapper(tmp_path).schema_problems("absent") == []

    def test_opens_an_existing_collection_as_is(self, tmp_path, legacy_table):
        table = self._wrapper(tmp_path).create_or_get_collection("images")
        assert table.count_rows() == 5
        assert "img_bytes" in table.schema.names

    def test_creates_a_missing_collection(self, tmp_path):
        table = self._wrapper(tmp_path).create_or_get_collection("fresh")
        assert "img_path" in table.schema.names

    def test_scalar_index_is_built_once(self, tmp_path, legacy_table):
        wrapper = self._wrapper(tmp_path)
        assert wrapper.ensure_scalar_index("images", "img_id") is True
        assert wrapper.ensure_scalar_index("images", "img_id") is False

    def test_a_failed_scalar_index_is_not_fatal(self, tmp_path):
        assert self._wrapper(tmp_path).ensure_scalar_index("absent", "img_id") is False


class TestInsertAfterMigration:
    def test_new_rows_land_in_the_migrated_columns(self, tmp_path):
        import logging

        import polars as pl

        from app.services.embedder import ImageEmbedder

        db = lancedb.connect(str(tmp_path / "biocosmos.lance"))
        vectors = pa.FixedSizeListArray.from_arrays(
            pa.array(np.zeros(DIMS, dtype=np.float32)), DIMS
        )
        # The migrated layout: `img_path` appended after the embeddings.
        table = db.create_table(
            "images",
            pa.table(
                {"img_id": ["a"], "unicom_embeddings": vectors, "img_path": ["p/a"]}
            ),
        )
        embedder = ImageEmbedder.__new__(ImageEmbedder)
        embedder.db_table = table
        embedder.logger = logging.getLogger("test")

        embedder._insert_batch_to_db(
            pl.DataFrame(
                {
                    "img_id": ["b"],
                    "img_path": ["p/b"],
                    "unicom_embeddings": [[1.0] * DIMS],
                }
            )
        )

        rows = {r["img_id"]: r["img_path"] for r in table.search().to_list()}
        assert rows == {"a": "p/a", "b": "p/b"}


class TestLanceSchema:
    def test_embeddings_are_fixed_size_float_vectors(self):
        """A variable-length list column cannot carry a vector index."""
        from app.database.model import LanceSchema

        schema = LanceSchema.to_arrow_schema()
        for column, dims in (("clip_embeddings", 512), ("unicom_embeddings", 768)):
            assert schema.field(column).type == pa.list_(pa.float32(), dims)
