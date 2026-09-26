"""The vector index build that startup will run if it is asked to.

Two things are tested here, and the split matters: `ensure_vector_index`
itself, which is idempotent and never fatal, and the startup caller, which
only runs it when `search_index.build_vector` says so. An ordinary boot pays
for neither.

The full-text half of this file went with the FTS stack it tested -- nothing
in the app ever ran a BM25 query, so both indexes were built on every start
and read by nothing.
"""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from lancedb import DBConnection


class _FakeIndex:
    def __init__(self, columns):
        self.columns = columns


class _FakeField:
    def __init__(self, list_size):
        self.type = MagicMock(list_size=list_size)


class TestEnsureVectorIndex:
    """Built once, never on a restart, and never fatal."""

    def _lance(self, table):
        from app.database.lance import LanceDB

        db = LanceDB.__new__(LanceDB)
        # The index build only looks a collection up by name.
        tables = {"images": table} if table is not None else {}
        db.db = cast(DBConnection, tables)
        return db

    def _table(self, *, rows, indices=(), dims=768):
        table = MagicMock()
        table.list_indices.return_value = [_FakeIndex(list(c)) for c in indices]
        table.count_rows.return_value = rows
        table.schema.field.return_value = _FakeField(dims)
        return table

    def test_builds_an_index_when_there_is_none(self):
        table = self._table(rows=640_000)
        assert (
            self._lance(table).ensure_vector_index("images", "unicom_embeddings")
            is True
        )

        (column,) = table.create_index.call_args.args
        config = table.create_index.call_args.kwargs["config"]
        assert column == "unicom_embeddings"
        assert config.distance_type == "cosine"
        # sqrt(640_000) == 800, and 768 dims at 8 per sub-vector.
        assert config.num_partitions == 800
        assert config.num_sub_vectors == 96

    def test_is_idempotent_across_restarts(self):
        """Training is minutes of work; a restart does not invalidate it."""
        table = self._table(rows=640_000, indices=[["unicom_embeddings"]])

        assert (
            self._lance(table).ensure_vector_index("images", "unicom_embeddings")
            is False
        )
        table.create_index.assert_not_called()

    def test_skips_a_collection_too_small_to_train_against(self):
        table = self._table(rows=100)

        assert (
            self._lance(table).ensure_vector_index("images", "unicom_embeddings")
            is False
        )
        table.create_index.assert_not_called()

    def test_partition_count_is_capped(self):
        """Past the cap, probing the partitions would cost more than it saves."""
        from app.database.lance import MAX_PARTITIONS, MIN_ROWS_FOR_INDEX

        huge = self._table(rows=10**12)
        self._lance(huge).ensure_vector_index("images", "unicom_embeddings")
        assert (
            huge.create_index.call_args.kwargs["config"].num_partitions
            == MAX_PARTITIONS
        )

        # No floor is needed, because the smallest collection that gets an
        # index at all already lands well clear of a degenerate partitioning.
        small = self._table(rows=MIN_ROWS_FOR_INDEX)
        self._lance(small).ensure_vector_index("images", "unicom_embeddings")
        assert small.create_index.call_args.kwargs["config"].num_partitions == 70

    def test_clip_width_also_divides_evenly(self):
        table = self._table(rows=640_000, dims=512)
        self._lance(table).ensure_vector_index("images", "clip_embeddings")
        assert table.create_index.call_args.kwargs["config"].num_sub_vectors == 64

    def test_a_failed_build_does_not_raise(self):
        """An unindexed column is slow, not broken."""
        table = self._table(rows=640_000)
        table.create_index.side_effect = RuntimeError("out of memory")

        assert (
            self._lance(table).ensure_vector_index("images", "unicom_embeddings")
            is False
        )

    def test_a_missing_collection_is_not_an_error(self):
        assert (
            self._lance(None).ensure_vector_index("images", "unicom_embeddings")
            is False
        )


class TestBuildSearchIndexes:
    """Which builds a start actually pays for."""

    def _app(self):
        app = MagicMock()
        app.state.lance_db = MagicMock()
        return app

    def _config(self, *, build_vector: bool):
        config = MagicMock()
        config.build_vector = build_vector
        return config

    def test_the_default_start_builds_no_index(self):
        """The regression that matters.

        `ImageConfig` must not even be constructed: `build_search_indexes` runs
        inside the lifespan `try` that re-raises, so anything constructed on
        the default path is a way for a boot to fail over work nobody asked
        for.
        """
        from app.main import build_search_indexes

        app = self._app()
        with (
            patch(
                "app.main.SearchIndexConfig",
                return_value=self._config(build_vector=False),
            ),
            patch("app.main.ImageConfig") as MockImageConfig,
        ):
            build_search_indexes(app)

        MockImageConfig.assert_not_called()
        app.state.lance_db.ensure_vector_index.assert_not_called()

    def test_the_flag_builds_both_embedding_columns(self):
        from app.main import build_search_indexes

        app = self._app()
        with (
            patch(
                "app.main.SearchIndexConfig",
                return_value=self._config(build_vector=True),
            ),
            patch("app.main.ImageConfig") as MockImageConfig,
        ):
            MockImageConfig.return_value.table = "nymphalidae"
            build_search_indexes(app)

        assert app.state.lance_db.ensure_vector_index.call_args_list == [
            (("nymphalidae", "unicom_embeddings"),),
            (("nymphalidae", "clip_embeddings"),),
        ]
        app.state.lance_db.ensure_scalar_index.assert_called_once_with(
            "nymphalidae", "img_id"
        )

    def test_a_skipped_build_says_which_flag_turned_it_off(self, caplog):
        """The whole readiness story, since there is no separate reporter.

        Without this the only signal that similarity search is scanning every
        row is that it feels slow.
        """
        import logging

        from app.main import build_search_indexes

        with (
            patch(
                "app.main.SearchIndexConfig",
                return_value=self._config(build_vector=False),
            ),
            caplog.at_level(logging.INFO, logger="app.main"),
        ):
            build_search_indexes(self._app())

        assert "search_index.build_vector" in caplog.text
        assert "config.yaml" in caplog.text

    def test_a_failed_build_is_not_fatal(self):
        """An unindexed column is slow, not broken."""
        from app.main import build_search_indexes

        app = self._app()
        app.state.lance_db.ensure_vector_index.side_effect = RuntimeError("oom")
        with (
            patch(
                "app.main.SearchIndexConfig",
                return_value=self._config(build_vector=True),
            ),
            patch("app.main.ImageConfig") as MockImageConfig,
        ):
            MockImageConfig.return_value.table = "nymphalidae"
            build_search_indexes(app)  # must not raise
