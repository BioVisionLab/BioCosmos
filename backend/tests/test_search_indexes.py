"""The index refresh that runs on every backend start.

Two different policies, and the difference is the point of these tests:
the DuckDB full-text indexes are rebuilt every start because the database
changes underneath a skipped ingestion, while the LanceDB vector indexes are
built once because training one is minutes of work that a restart does not
invalidate.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestFullTextReindex:
    """Rebuilt on every start, including when ingestion is skipped."""

    def _image_service(self, *, skip: bool, table_exists: bool):
        from app.services.metadata import ImageMetaService

        service = ImageMetaService.__new__(ImageMetaService)
        service.table = "image_meta"
        service.skip_ingestion = skip
        service.db_client = MagicMock()
        service.db_client.table_exists.return_value = table_exists
        return service

    def test_reindex_runs_even_when_ingestion_is_skipped(self):
        """The case this exists for.

        Ingestion is normally skipped in production, so `ingest` returns before
        it would have rebuilt the index -- and the DuckDB file still changes
        underneath, through a geoharmonize or colharmonize run. Without this
        the index describes rows that may no longer be there.
        """
        from app.services.metadata import (
            IMAGE_META_COLUMNS_INDEXED,
            IMAGE_META_INDEX_ID,
        )

        service = self._image_service(skip=True, table_exists=True)

        assert service.reindex() is True
        service.db_client.index_table.assert_called_once_with(
            table_name="image_meta",
            id_column=IMAGE_META_INDEX_ID,
            columns=IMAGE_META_COLUMNS_INDEXED,
            overwrite=True,
        )

    def test_reindex_skips_a_table_that_does_not_exist(self):
        service = self._image_service(skip=True, table_exists=False)

        assert service.reindex() is False
        service.db_client.index_table.assert_not_called()

    def test_a_failed_reindex_does_not_raise(self):
        """A stale index still answers; a backend that will not boot does not."""
        service = self._image_service(skip=True, table_exists=True)
        service.db_client.index_table.side_effect = RuntimeError("disk full")

        assert service.reindex() is False

    def test_gbif_reindex_rebuilds_its_own_index(self):
        from app.services.gbif import (
            GBIF_COLUMNS_INDEXED,
            GBIF_INDEX_ID,
            GbifPersistData,
        )

        service = GbifPersistData.__new__(GbifPersistData)
        service.table_name = "gbif_meta"
        service.db_client = MagicMock()
        service.db_client.table_exists.return_value = True

        assert service.reindex() is True
        service.db_client.index_table.assert_called_once_with(
            table_name="gbif_meta",
            id_column=GBIF_INDEX_ID,
            columns=GBIF_COLUMNS_INDEXED,
            overwrite=True,
        )


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
        db.db = {"images": table} if table is not None else {}
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

        kwargs = table.create_index.call_args.kwargs
        assert kwargs["metric"] == "cosine"
        assert kwargs["vector_column_name"] == "unicom_embeddings"
        # sqrt(640_000) == 800, and 768 dims at 8 per sub-vector.
        assert kwargs["num_partitions"] == 800
        assert kwargs["num_sub_vectors"] == 96

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
        assert huge.create_index.call_args.kwargs["num_partitions"] == MAX_PARTITIONS

        # No floor is needed, because the smallest collection that gets an
        # index at all already lands well clear of a degenerate partitioning.
        small = self._table(rows=MIN_ROWS_FOR_INDEX)
        self._lance(small).ensure_vector_index("images", "unicom_embeddings")
        assert small.create_index.call_args.kwargs["num_partitions"] == 70

    def test_clip_width_also_divides_evenly(self):
        table = self._table(rows=640_000, dims=512)
        self._lance(table).ensure_vector_index("images", "clip_embeddings")
        assert table.create_index.call_args.kwargs["num_sub_vectors"] == 64

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
