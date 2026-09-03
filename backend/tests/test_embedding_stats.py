"""Tests for the embedding distribution service and query layer."""

import polars as pl
import pytest
from unittest.mock import MagicMock, patch

from app.query.embedding_stats import EmbeddingDistribution
from app.services import embedding_stats as stats_module
from app.services.embedding_stats import EmbeddingStatsService
from tests.conftest import FakeLanceDB, FakeLanceTable


CLIP_DIMS = 4
UNICOM_DIMS = 6


def _embedding_frame(rows: int = 8) -> pl.DataFrame:
    """Build a small frame shaped like the real LanceDB embedding table."""
    return pl.DataFrame(
        {
            "clip_embeddings": [
                [float(i + j) for j in range(CLIP_DIMS)] for i in range(rows)
            ],
            "unicom_embeddings": [
                [float(i - j) for j in range(UNICOM_DIMS)] for i in range(rows)
            ],
        }
    )


@pytest.fixture(autouse=True)
def clear_cache():
    """Keep the module-level cache from leaking between tests."""
    stats_module._CACHE = None
    yield
    stats_module._CACHE = None


def _make_service(frame: pl.DataFrame | None = None) -> EmbeddingStatsService:
    table = FakeLanceTable(frame if frame is not None else _embedding_frame())
    lance_db = FakeLanceDB(table)
    with patch("app.services.embedding_stats.ImageConfig") as MockConfig:
        MockConfig.return_value.table = "nymphalidae"
        return EmbeddingStatsService(lance_db=lance_db)


# ===========================================================================
# Service
# ===========================================================================

class TestEmbeddingStatsService:
    def test_returns_one_summary_per_model(self):
        result = _make_service().get_distributions()

        assert result is not None
        assert [d["embedding_model"] for d in result] == ["CLIP", "UNICOM"]

    def test_quantiles_are_ordered(self):
        result = _make_service().get_distributions()

        assert result is not None
        for summary in result:
            assert (
                summary["minimum"]
                <= summary["lower_whisker"]
                <= summary["q1"]
                <= summary["median"]
                <= summary["q3"]
                <= summary["upper_whisker"]
                <= summary["maximum"]
            )

    def test_pools_every_component_value(self):
        frame = _embedding_frame(rows=8)
        result = _make_service(frame).get_distributions()

        assert result is not None
        clip, unicom = result
        assert clip["image_count"] == 8
        assert clip["sample_size"] == 8 * CLIP_DIMS
        assert unicom["sample_size"] == 8 * UNICOM_DIMS

    def test_reports_model_dimensions(self):
        with patch(
            "app.services.embedding_stats.get_clip_ndims", return_value=512
        ), patch(
            "app.services.embedding_stats.get_unicom_ndims", return_value=768
        ):
            result = _make_service().get_distributions()

        assert result is not None
        assert result[0]["dimensions"] == 512
        assert result[1]["dimensions"] == 768

    def test_empty_table_returns_none(self):
        service = _make_service(pl.DataFrame())

        assert service.get_distributions() is None

    def test_read_failure_returns_none(self):
        service = _make_service()
        service._read_sample = MagicMock(side_effect=RuntimeError("boom"))

        assert service.get_distributions() is None

    def test_sample_is_bounded(self):
        frame = _embedding_frame(rows=stats_module.SAMPLE_SIZE + 25)
        result = _make_service(frame).get_distributions()

        assert result is not None
        assert result[0]["image_count"] == stats_module.SAMPLE_SIZE

    def test_large_table_is_sampled_in_spread_chunks(self):
        """A big table must not be summarized from one contiguous block."""
        rows = stats_module.SAMPLE_SIZE * 4
        service = _make_service(_embedding_frame(rows=rows))
        service._read_chunk = MagicMock(wraps=service._read_chunk)

        result = service.get_distributions()

        assert result is not None
        offsets = [call.args[0] for call in service._read_chunk.call_args_list]
        assert len(offsets) == stats_module.SAMPLE_CHUNKS
        assert offsets == sorted(offsets)
        assert offsets[0] == 0
        # The last chunk must start well past the head of the table.
        assert offsets[-1] > rows // 2
        assert result[0]["image_count"] == stats_module.SAMPLE_SIZE

    def test_small_table_is_read_in_one_chunk(self):
        service = _make_service(_embedding_frame(rows=12))
        service._read_chunk = MagicMock(wraps=service._read_chunk)

        result = service.get_distributions()

        assert result is not None
        assert service._read_chunk.call_count == 1
        assert result[0]["image_count"] == 12

    def test_second_call_uses_cache(self):
        service = _make_service()
        service._read_sample = MagicMock(wraps=service._read_sample)

        first = service.get_distributions()
        second = service.get_distributions()

        assert first == second
        assert service._read_sample.call_count == 1


# ===========================================================================
# Query layer
# ===========================================================================

class TestEmbeddingDistribution:
    def test_payload_is_camel_cased(self, fake_request):
        query = EmbeddingDistribution(request=fake_request)
        with patch(
            "app.query.embedding_stats.EmbeddingStatsService"
        ) as MockService:
            MockService.return_value.get_distributions.return_value = [
                {
                    "embedding_model": "CLIP",
                    "dimensions": 512,
                    "image_count": 10,
                    "sample_size": 5120,
                    "minimum": -1.0,
                    "q1": -0.5,
                    "median": 0.0,
                    "q3": 0.5,
                    "maximum": 1.0,
                    "lower_whisker": -1.0,
                    "upper_whisker": 1.0,
                    "mean": 0.0,
                    "std_dev": 0.5,
                }
            ]
            result = query.get_distributions()

        assert result is not None
        summary = result["distributions"][0]
        assert summary["embeddingModel"] == "CLIP"
        assert summary["lowerWhisker"] == -1.0
        assert summary["stdDev"] == 0.5
        assert summary["imageCount"] == 10

    def test_returns_none_when_service_has_no_data(self, fake_request):
        query = EmbeddingDistribution(request=fake_request)
        with patch(
            "app.query.embedding_stats.EmbeddingStatsService"
        ) as MockService:
            MockService.return_value.get_distributions.return_value = None

            assert query.get_distributions() is None

    def test_returns_none_on_service_error(self, fake_request):
        query = EmbeddingDistribution(request=fake_request)
        with patch(
            "app.query.embedding_stats.EmbeddingStatsService",
            side_effect=RuntimeError("boom"),
        ):
            assert query.get_distributions() is None
