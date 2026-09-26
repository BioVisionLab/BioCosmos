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
    "col": {
        "file": "NameUsage.tsv",
        "vernacular_file": "VernacularName.tsv",
        "table": "col_taxonomy",
        "vernacular_table": "col_vernacular",
        "clade_rank": "order",
        "clade_value": "Lepidoptera",
        "matches_table": "col_taxonomy_matches",
        "variants_table": "col_taxon_variants",
        "candidates_table": "col_taxonomy_candidates",
        "occurrence_status_table": "image_meta_taxonomy",
        "skip": True,
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
        return_value={
            **MOCK_CONFIG,
            "images": {**MOCK_CONFIG["images"], "max_resolution": -100},
        },
    )
    def test_max_resolution_negative_ignored(self, _mock):
        from app.configs.config import ImageConfig

        cfg = ImageConfig()
        assert cfg.max_resolution is None

    @patch(
        "app.configs.config.load_config",
        return_value={
            **MOCK_CONFIG,
            "images": {**MOCK_CONFIG["images"], "thumbnail_resolution": -1},
        },
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

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_source_table_and_exclusions_default(self, _mock):
        from app.configs.config import ImageMetaConfig

        cfg = ImageMetaConfig()
        assert cfg.source_table == "image_meta_source"
        assert cfg.exclude_families == []

    @patch(
        "app.configs.config.load_config",
        return_value={
            **MOCK_CONFIG,
            "image_metadata": {
                **MOCK_CONFIG["image_metadata"],
                "exclude_families": [" Castniidae ", "castniidae", ""],
            },
        },
    )
    def test_exclude_families_normalized(self, _mock):
        from app.configs.config import ImageMetaConfig

        assert ImageMetaConfig().exclude_families == ["castniidae"]

    def test_shipped_config_excludes_castniidae(self):
        from app.configs.config import ImageMetaConfig

        assert "castniidae" in ImageMetaConfig().exclude_families

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
        return_value={
            **MOCK_CONFIG,
            "embedder": {**MOCK_CONFIG["embedder"], "batch_size": -5},
        },
    )
    def test_batch_size_negative_falls_back(self, _mock):
        from app.configs.config import EmbedderConfig

        cfg = EmbedderConfig()
        assert cfg.batch_size == 8


class TestOpenAIConfig:
    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_model(self, _mock, monkeypatch):
        monkeypatch.delenv("LLM_MODEL", raising=False)
        from app.configs.config import OpenAIConfig

        cfg = OpenAIConfig()
        assert cfg.model == "mistral-small-3.1"

    @pytest.mark.parametrize("override", ["custom-model", "  custom-model  "])
    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_model_env_override(self, _mock, monkeypatch, override):
        from app.configs.config import OpenAIConfig

        monkeypatch.setenv("LLM_MODEL", override)
        assert OpenAIConfig().model == "custom-model"

    @pytest.mark.parametrize("override", ["", "   "])
    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_blank_model_override_uses_yaml(self, _mock, monkeypatch, override):
        from app.configs.config import OpenAIConfig

        monkeypatch.setenv("LLM_MODEL", override)
        assert OpenAIConfig().model == "mistral-small-3.1"

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


class TestColConfig:
    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_tables(self, _mock):
        from app.configs.config import ColConfig

        cfg = ColConfig()
        assert cfg.table == "col_taxonomy"
        assert cfg.vernacular_table == "col_vernacular"
        assert cfg.matches_table == "col_taxonomy_matches"
        assert cfg.variants_table == "col_taxon_variants"
        assert cfg.candidates_table == "col_taxonomy_candidates"
        assert cfg.occurrence_status_table == "image_meta_taxonomy"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_skip_true(self, _mock):
        from app.configs.config import ColConfig

        assert ColConfig().skip is True

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "col": {**MOCK_CONFIG["col"], "skip": "no"}},
    )
    def test_skip_string_no(self, _mock):
        from app.configs.config import ColConfig

        assert ColConfig().skip is False

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_paths_from_env(self, _mock):
        from app.configs.config import ColConfig

        with patch.dict(os.environ, {"COL_DIR": "/mnt/col"}):
            cfg = ColConfig()
            assert cfg.path == "/mnt/col/NameUsage.tsv"
            assert cfg.vernacular_path == "/mnt/col/VernacularName.tsv"

    @patch(
        "app.configs.config.load_config",
        return_value={
            **MOCK_CONFIG,
            "col": {**MOCK_CONFIG["col"], "cache_dir": "col_cache"},
        },
    )
    def test_relative_cache_dir_resolves_under_duck_dir(self, _mock):
        from app.configs.config import ColConfig

        with patch.dict(os.environ, {"DUCK_DIR": "/data/duck"}):
            assert ColConfig().cache_dir == "/data/duck/col_cache"

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_clade_filter(self, _mock):
        from app.configs.config import ColConfig

        cfg = ColConfig()
        assert cfg.clade_rank == "order"
        assert cfg.clade_value == "Lepidoptera"

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "col": {**MOCK_CONFIG["col"], "clade_value": ""}},
    )
    def test_empty_clade_value_means_all_of_col(self, _mock):
        from app.configs.config import ColConfig

        assert ColConfig().clade_value is None

    @patch("app.configs.config.load_config", return_value={})
    def test_defaults_without_a_col_stanza(self, _mock):
        from app.configs.config import ColConfig

        cfg = ColConfig()
        assert cfg.table == "col_taxonomy"
        assert cfg.clade_value is None
        assert cfg.skip is False
        # Unset, the reference index is shared with the colharmonize CLI.
        assert cfg.cache_dir.endswith(".cache/colharmonize")


class TestAppSettings:
    """COL_DIR is optional so a host without the CoL release still boots."""

    def test_settings_load_without_col_dir(self):
        from app.main import AppSettings

        settings = AppSettings(
            DUCK_DIR=".",
            LANCE_DIR=".",
            IMAGE_DIR=".",
            IMAGE_META_DIR=".",
            GBIF_DIR=".",
            COL_DIR=None,
        )
        assert settings.COL_DIR is None

    def test_a_missing_required_dir_still_fails(self):
        from pydantic import ValidationError

        from app.main import AppSettings

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                # pydantic-settings accepts `_env_file` at runtime, but its
                # dataclass_transform signature lists only the model fields.
                AppSettings(_env_file=None)  # pyright: ignore[reportCallIssue]


class TestLocalityConfig:
    """The locality block is optional in the YAML, so the defaults matter."""

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_defaults_when_the_block_is_absent(self, _mock):
        from app.configs.config import LocalityConfig

        cfg = LocalityConfig()
        assert cfg.skip is False
        assert cfg.table == "image_meta_locality"
        assert cfg.coordinates_table == "image_meta_coordinates"

    @patch(
        "app.configs.config.load_config",
        return_value={
            **MOCK_CONFIG,
            "locality": {
                "skip": "yes",
                "table": "custom_locality",
                "coordinates_table": "custom_coordinates",
            },
        },
    )
    def test_reads_the_block(self, _mock):
        from app.configs.config import LocalityConfig

        cfg = LocalityConfig()
        assert cfg.skip is True
        assert cfg.table == "custom_locality"
        assert cfg.coordinates_table == "custom_coordinates"


class TestSearchIndexConfig:
    """The vector index build is off unless the YAML asks for it."""

    @patch("app.configs.config.load_config", return_value=MOCK_CONFIG)
    def test_the_flag_is_off_when_the_stanza_is_absent(self, _mock):
        """A config.yaml written before this flag existed builds nothing.

        MOCK_CONFIG deliberately has no `search_index` key, which is exactly
        the state of every deployment's config.yaml the day this ships.
        """
        from app.configs.config import SearchIndexConfig

        assert SearchIndexConfig().build_vector is False

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "search_index": {"build_vector": True}},
    )
    def test_reads_the_flag_from_the_yaml(self, _mock):
        from app.configs.config import SearchIndexConfig

        assert SearchIndexConfig().build_vector is True

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "search_index": {"build_vector": "yes"}},
    )
    def test_accepts_the_string_spellings(self, _mock):
        """Matches the coercion the nine `skip` properties already do."""
        from app.configs.config import SearchIndexConfig

        assert SearchIndexConfig().build_vector is True

    @patch(
        "app.configs.config.load_config",
        return_value={**MOCK_CONFIG, "search_index": {"build_vector": 3}},
    )
    def test_a_non_boolean_is_treated_as_off(self, _mock):
        """Fail safe: a typo must not cost a surprise multi-minute build."""
        from app.configs.config import SearchIndexConfig

        assert SearchIndexConfig().build_vector is False


class TestNcbiConfig:
    @pytest.mark.parametrize(
        "raw", ["abc123", '"abc123"', "'abc123'", '  " abc123 "  ']
    )
    def test_strips_quotes_from_credentials(self, monkeypatch, raw):
        """A quoted key reaches NCBI verbatim and is rejected with a 400."""
        from app.configs.config import NcbiConfig

        monkeypatch.setenv("NCBI_API_KEY", raw)
        monkeypatch.setenv("NCBI_EMAIL", raw.replace("abc123", "me@example.org"))
        assert NcbiConfig().api_key == "abc123"
        assert NcbiConfig().email == "me@example.org"

    @pytest.mark.parametrize("raw", ["", "   ", '""', "''"])
    def test_blank_or_empty_quotes_are_unset(self, monkeypatch, raw):
        from app.configs.config import NcbiConfig

        monkeypatch.setenv("NCBI_API_KEY", raw)
        monkeypatch.setenv("NCBI_EMAIL", raw)
        monkeypatch.setenv("CROSSREF_MAILTO", "fallback@example.org")
        assert NcbiConfig().api_key is None
        assert NcbiConfig().email == "fallback@example.org"

    def test_mismatched_quotes_are_kept(self, monkeypatch):
        from app.configs.config import NcbiConfig

        monkeypatch.setenv("NCBI_API_KEY", "\"abc123'")
        assert NcbiConfig().api_key == "\"abc123'"
