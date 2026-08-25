"""Tests for config classes in app.configs.config."""

import os
import pytest
from unittest.mock import patch, MagicMock


# We need to patch load_config before importing the config classes,
# so we import inside each test method.


MOCK_CONFIG = {
    "images": {
        "dir": "./images",
        "format": "webp",
        "max_resolution": 800,
        "thumbnail_resolution": 128,
        "processed_dir": "static/webp",
        "table": "nymphalidae",
        "limit": None,
    },
    "image_metadata": {
        "file": "combined_meta.parquet",
        "format": "parquet",
        "skip": False,
        "table": "image_meta",
    },
    "embedder": {
        "device": "cpu",
        "batch_size": 32,
        "reset": False,
        "skip": True,
    },
    "openai": {
        "model": "mistral-small-3.1",
    },
    "db": {
        "duck": {"file": "biocosmos.duckdb"},
        "lance": {"file": "biocosmos.lance"},
    },
}


class TestImageConfig:

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_format(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.format == "webp"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_max_resolution(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.max_resolution == 800

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_thumbnail_resolution(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.thumbnail_resolution == 128

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_processed_dir(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.processed_dir == "static/webp"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_thumbnail_dir_computed(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.thumbnail_dir == "static/webp/thumbnails"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_table_default(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.table == "nymphalidae"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_limit_none(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.limit is None

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "images": {**MOCK_CONFIG["images"], "limit": 500}},
    )
    def test_limit_positive(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.limit == 500

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "images": {**MOCK_CONFIG["images"], "limit": -1}},
    )
    def test_limit_negative_ignored(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.limit is None

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "images": {**MOCK_CONFIG["images"], "max_resolution": -100}},
    )
    def test_max_resolution_negative_ignored(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.max_resolution is None

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "images": {**MOCK_CONFIG["images"], "thumbnail_resolution": -1}},
    )
    def test_thumbnail_resolution_negative_falls_back(self, _mock):
        from app.configs.config import ImageConfig
        cfg = ImageConfig()
        assert cfg.thumbnail_resolution == 128

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_dir_from_env(self, _mock):
        from app.configs.config import ImageConfig
        with patch.dict(os.environ, {"IMAGE_DIR": "/mnt/images"}):
            cfg = ImageConfig()
            assert cfg.dir == "/mnt/images"


class TestImageMetaConfig:

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_format(self, _mock):
        from app.configs.config import ImageMetaConfig
        cfg = ImageMetaConfig()
        assert cfg.format == "parquet"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_skip_false(self, _mock):
        from app.configs.config import ImageMetaConfig
        cfg = ImageMetaConfig()
        assert cfg.skip is False

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_table(self, _mock):
        from app.configs.config import ImageMetaConfig
        cfg = ImageMetaConfig()
        assert cfg.table == "image_meta"

    @patch(
        "app.configs.config.load_config",
        return_value={
            **MOCK_CONFIG,
            "image_metadata": {**MOCK_CONFIG["image_metadata"], "skip": "yes"},
        },
    )
    def test_skip_string_yes(self, _mock):
        from app.configs.config import ImageMetaConfig
        cfg = ImageMetaConfig()
        assert cfg.skip is True


class TestEmbedderConfig:

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_device_cpu(self, _mock):
        from app.configs.config import EmbedderConfig
        cfg = EmbedderConfig()
        assert cfg.device == "cpu"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_batch_size(self, _mock):
        from app.configs.config import EmbedderConfig
        cfg = EmbedderConfig()
        assert cfg.batch_size == 32

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_skip_true(self, _mock):
        from app.configs.config import EmbedderConfig
        cfg = EmbedderConfig()
        assert cfg.skip is True

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_reset_false(self, _mock):
        from app.configs.config import EmbedderConfig
        cfg = EmbedderConfig()
        assert cfg.reset is False

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "embedder": {**MOCK_CONFIG["embedder"], "batch_size": -5}},
    )
    def test_batch_size_negative_falls_back(self, _mock):
        from app.configs.config import EmbedderConfig
        cfg = EmbedderConfig()
        assert cfg.batch_size == 8


class TestOpenAIConfig:

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_model(self, _mock):
        from app.configs.config import OpenAIConfig
        cfg = OpenAIConfig()
        assert cfg.model == "mistral-small-3.1"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_api_url_from_env(self, _mock):
        from app.configs.config import OpenAIConfig
        with patch.dict(os.environ, {"LLM_API_URL": "http://localhost:8080"}):
            cfg = OpenAIConfig()
            assert cfg.api_url == "http://localhost:8080"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_api_url_none_when_unset(self, _mock):
        from app.configs.config import OpenAIConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = OpenAIConfig()
            assert cfg.api_url is None

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_api_key_none_when_unset(self, _mock):
        from app.configs.config import OpenAIConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = OpenAIConfig()
            assert cfg.api_key is None
