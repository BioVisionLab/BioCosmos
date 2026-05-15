"""Tests for ImagePersistData (services/images.py)."""

import numpy as np
import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import FakeLanceDB, FakeLanceTable, FakeDuckDBClient


class TestImagePersistData:
    """Unit tests for ImagePersistData search and filter methods."""

    def _make_instance(self, lance_table=None, duckdb=None):
        """Create an ImagePersistData with fakes, patching ImageConfig."""
        table = lance_table or FakeLanceTable()
        lance = FakeLanceDB(table)
        duck = duckdb or FakeDuckDBClient()

        with patch("app.services.images.ImageConfig") as MockCfg:
            MockCfg.return_value.table = "nymphalidae"
            from app.services.images import ImagePersistData
            return ImagePersistData(lance_db=lance, duckdb=duck)

    # ------------------------------------------------------------------
    # get_img_path_by_id
    # ------------------------------------------------------------------

    def test_get_img_path_by_id_found(self):
        df = pl.DataFrame({"img_id": ["img-001"], "img_path": ["/data/img-001.webp"]})
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)
        result = persist.get_img_path_by_id("img-001")
        assert result == "/data/img-001.webp"

    def test_get_img_path_by_id_not_found(self):
        table = FakeLanceTable(pl.DataFrame())
        persist = self._make_instance(lance_table=table)
        result = persist.get_img_path_by_id("missing")
        assert result is None

    # ------------------------------------------------------------------
    # fetch_image_path
    # ------------------------------------------------------------------

    def test_fetch_image_path_success(self):
        df = pl.DataFrame({"img_id": ["img-001"], "img_path": ["/data/img-001.webp"]})
        table = FakeLanceTable(df)

        with patch("app.services.images.ImageMetaService") as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = ["img-001"]
            persist = self._make_instance(lance_table=table)
            result = persist.fetch_image_path("danaus plexippus")

        assert result == "/data/img-001.webp"

    def test_fetch_image_path_no_ids(self):
        with patch("app.services.images.ImageMetaService") as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = []
            persist = self._make_instance()
            result = persist.fetch_image_path("nonexistent")

        assert result is None

    # ------------------------------------------------------------------
    # _filter_by_species
    # ------------------------------------------------------------------

    def test_filter_by_species_keeps_best_per_species(self):
        df = pl.DataFrame({
            "imgId": ["img-001", "img-002", "img-003"],
            "species": ["species_a", "species_a", "species_b"],
            "distance": [0.5, 0.3, 0.1],
        })
        persist = self._make_instance()
        result = persist._filter_by_species(df)

        assert len(result) == 2
        # species_a should keep the one with lower distance (0.3)
        species_a = result.filter(pl.col("species") == "species_a")
        assert species_a["distance"][0] == 0.3

    def test_filter_by_species_handles_none(self):
        persist = self._make_instance()
        result = persist._filter_by_species(None)
        assert result is None

    # ------------------------------------------------------------------
    # _query_embedding with distance filter
    # ------------------------------------------------------------------

    def test_query_embedding_distance_filter(self):
        """Results above max_distance should be filtered out."""
        df = pl.DataFrame({
            "img_id": ["img-001", "img-002", "img-003"],
            "_distance": [0.1, 0.5, 1.5],
        })
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
            max_distance=0.8,
        )
        assert result is not None
        assert len(result) == 2  # only 0.1 and 0.5

    def test_query_embedding_no_distance_filter(self):
        """Without max_distance, all results should pass."""
        df = pl.DataFrame({
            "img_id": ["img-001", "img-002"],
            "_distance": [0.1, 1.9],
        })
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
        )
        assert result is not None
        assert len(result) == 2

    def test_query_embedding_deduplicates_by_img_id(self):
        """Duplicate img_ids should be removed."""
        df = pl.DataFrame({
            "img_id": ["img-001", "img-001"],
            "_distance": [0.1, 0.2],
        })
        table = FakeLanceTable(df)
        persist = self._make_instance(lance_table=table)

        result = persist._query_embedding(
            query_vector=np.zeros(512),
            vector_column_name="clip_embeddings",
            limit=10,
        )
        assert len(result) == 1

    # ------------------------------------------------------------------
    # SpeciesImage model
    # ------------------------------------------------------------------

    def test_species_image_to_dict(self):
        from app.services.images import SpeciesImage

        si = SpeciesImage(species="danaus_plexippus", imageIds=["img-001", "img-002"])
        d = si.to_dict()
        assert d["species"] == "danaus_plexippus"
        assert len(d["imageIds"]) == 2
