"""Tests for ImageMetaRetrieval and ImageFileRetrieval."""

import os
import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from app.query.image_files import ImageMetaRetrieval, ImageFileRetrieval


# =========================================================================
# ImageMetaRetrieval
# =========================================================================

class TestImageMetaRetrieval:

    def test_get_species_image_ids_returns_list(self, fake_request):
        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = [
                "img-001", "img-002"
            ]
            retrieval = ImageMetaRetrieval(request=fake_request)
            ids = retrieval.get_species_image_ids("danaus plexippus")
            assert ids == ["img-001", "img-002"]

    def test_get_species_image_ids_empty(self, fake_request):
        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_image_ids_by_species.return_value = []
            retrieval = ImageMetaRetrieval(request=fake_request)
            ids = retrieval.get_species_image_ids("nonexistent species")
            assert ids == []

    def test_get_meta_by_id_returns_filtered_dict(self, fake_request):
        meta_df = pl.DataFrame({
            "license": ["CC-BY"],
            "uuid": ["abc-123"],
            "uri": ["https://example.com/img.png"],
            "class_dv": ["dorsal"],
            "lat": [40.7],
            "lon": [-74.0],
            "source_db": ["MCZ"],
            "internal_field": ["secret"],  # should be filtered out
        })
        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_meta_by_image_id.return_value = meta_df
            retrieval = ImageMetaRetrieval(request=fake_request)
            meta = retrieval.get_meta_by_id("img-001")

        assert meta is not None
        assert "license" in meta
        assert "internal_field" not in meta
        assert meta["source_db"] == "MCZ"

    def test_get_meta_by_id_returns_none_when_empty(self, fake_request):
        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_meta_by_image_id.return_value = pl.DataFrame()
            retrieval = ImageMetaRetrieval(request=fake_request)
            meta = retrieval.get_meta_by_id("missing-id")
            assert meta is None

    def test_get_meta_by_id_returns_none_on_error(self, fake_request):
        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_meta_by_image_id.side_effect = Exception("db error")
            retrieval = ImageMetaRetrieval(request=fake_request)
            meta = retrieval.get_meta_by_id("img-001")
            assert meta is None


# =========================================================================
# ImageFileRetrieval
# =========================================================================

class TestImageFileRetrieval:

    @patch("app.query.image_files.ImageConfig")
    def _make_retrieval(self, fake_request, MockConfig, fmt="webp", processed="static/webp"):
        cfg = MockConfig.return_value
        cfg.format = fmt
        cfg.processed_dir = processed
        cfg.thumbnail_dir = os.path.join(processed, "thumbnails")
        return ImageFileRetrieval(request=fake_request)

    def test_get_thumbnail_returns_path_when_exists(self, fake_request, tmp_path):
        thumb_dir = tmp_path / "thumbnails"
        thumb_dir.mkdir()
        thumb_file = thumb_dir / "img-001_thumbnail.webp"
        thumb_file.write_bytes(b"fake image data")

        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path)
            cfg.thumbnail_dir = str(thumb_dir)
            retrieval = ImageFileRetrieval(request=fake_request)

        result = retrieval.get_thumbnail("img-001")
        assert result is not None
        assert result.endswith("img-001_thumbnail.webp")

    def test_get_thumbnail_returns_none_when_missing(self, fake_request, tmp_path):
        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path)
            cfg.thumbnail_dir = str(tmp_path / "thumbnails")
            retrieval = ImageFileRetrieval(request=fake_request)

        result = retrieval.get_thumbnail("missing-img")
        assert result is None

    def test_get_full_res_returns_static_path_when_exists(self, fake_request, tmp_path):
        img_file = tmp_path / "img-001.webp"
        img_file.write_bytes(b"image data")

        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path)
            cfg.thumbnail_dir = str(tmp_path / "thumbnails")
            retrieval = ImageFileRetrieval(request=fake_request)

        result = retrieval.get_full_res("img-001")
        assert result is not None
        assert result.endswith("img-001.webp")

    def test_get_full_res_falls_back_to_lancedb(self, fake_request, tmp_path):
        """When static file missing, falls back to LanceDB img_path."""
        lance_path = str(tmp_path / "fallback.png")
        # Create the fallback file
        (tmp_path / "fallback.png").write_bytes(b"fallback data")

        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path / "nonexistent")
            cfg.thumbnail_dir = str(tmp_path / "nonexistent" / "thumbnails")
            retrieval = ImageFileRetrieval(request=fake_request)

        with patch(
            "app.query.image_files.ImagePersistData"
        ) as MockPersist:
            MockPersist.return_value.get_img_path_by_id.return_value = lance_path
            result = retrieval.get_full_res("img-001")

        assert result == lance_path

    def test_get_full_res_returns_none_when_all_missing(self, fake_request, tmp_path):
        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path / "nonexistent")
            cfg.thumbnail_dir = str(tmp_path / "nonexistent" / "thumbnails")
            retrieval = ImageFileRetrieval(request=fake_request)

        with patch(
            "app.query.image_files.ImagePersistData"
        ) as MockPersist:
            MockPersist.return_value.get_img_path_by_id.return_value = None
            result = retrieval.get_full_res("missing-img")

        assert result is None

    def test_get_species_thumbnail_delegates(self, fake_request, tmp_path):
        thumb_dir = tmp_path / "thumbnails"
        thumb_dir.mkdir()
        thumb_file = thumb_dir / "img-001_thumbnail.webp"
        thumb_file.write_bytes(b"thumb")

        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path)
            cfg.thumbnail_dir = str(thumb_dir)
            retrieval = ImageFileRetrieval(request=fake_request)

        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_species_main_image_id.return_value = "img-001"
            result = retrieval.get_species_thumbnail("danaus plexippus")

        assert result is not None
        assert "img-001_thumbnail.webp" in result

    def test_get_species_thumbnail_returns_none_when_no_image_id(self, fake_request, tmp_path):
        with patch("app.query.image_files.ImageConfig") as MockConfig:
            cfg = MockConfig.return_value
            cfg.format = "webp"
            cfg.processed_dir = str(tmp_path)
            cfg.thumbnail_dir = str(tmp_path / "thumbnails")
            retrieval = ImageFileRetrieval(request=fake_request)

        with patch(
            "app.query.image_files.ImageMetaService"
        ) as MockMeta:
            MockMeta.return_value.get_species_main_image_id.return_value = None
            result = retrieval.get_species_thumbnail("nonexistent")

        assert result is None
