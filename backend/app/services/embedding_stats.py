import logging
import threading

import numpy as np
import polars as pl

from ..configs.config import ImageConfig
from ..database.lance import LanceDB
from .clip import get_clip_ndims
from .unicom import get_unicom_ndims

logger = logging.getLogger(__name__)

# Maximum number of image rows read from LanceDB when summarizing the
# embedding spaces. Each row carries 512 CLIP + 768 UNICOM floats, so a
# full-table scan is expensive; a bounded sample is enough to describe the
# distribution of component values.
SAMPLE_SIZE = 5000

# Rows come back in storage order, which tracks ingestion and is therefore
# correlated with species. Reading one contiguous block would describe a
# narrow slice of the collection, so the sample is spread over this many
# evenly spaced chunks instead.
SAMPLE_CHUNKS = 10

CLIP_COLUMN = "clip_embeddings"
UNICOM_COLUMN = "unicom_embeddings"

# The summary is stable for the lifetime of the process (the embeddings only
# change through an offline ingestion run), so it is computed once and reused.
_CACHE: list[dict] | None = None
_CACHE_LOCK = threading.Lock()


def _summarize(
    name: str, dimensions: int, images: int, values: np.ndarray
) -> dict:
    """Build a five-number summary with Tukey whiskers for one model."""
    q1, median, q3 = (float(q) for q in np.percentile(values, [25, 50, 75]))
    minimum = float(values.min())
    maximum = float(values.max())
    iqr = q3 - q1

    return {
        "embedding_model": name,
        "dimensions": dimensions,
        "image_count": images,
        "sample_size": int(values.size),
        "minimum": minimum,
        "q1": q1,
        "median": median,
        "q3": q3,
        "maximum": maximum,
        # Clamp the fences to the observed range so the whiskers never
        # extend past real data.
        "lower_whisker": max(minimum, q1 - 1.5 * iqr),
        "upper_whisker": min(maximum, q3 + 1.5 * iqr),
        "mean": float(values.mean()),
        "std_dev": float(values.std()),
    }


class EmbeddingStatsService:
    """Summarize the distribution of CLIP and UNICOM embedding values."""

    def __init__(self, lance_db: LanceDB):
        self.config = ImageConfig()
        self.lance_db = lance_db
        self.db_table = lance_db.create_or_get_collection(self.config.table)

    def _read_chunk(self, offset: int, limit: int) -> pl.DataFrame:
        """Read one projected chunk of both embedding columns.

        Goes through the search builder rather than the table's lazy
        `to_polars()`, which is broken by the pinned polars/lancedb pair.
        """
        return (
            self.db_table.search()
            .select([CLIP_COLUMN, UNICOM_COLUMN])
            .offset(offset)
            .limit(limit)
            .to_polars()
        )

    def _read_sample(self) -> pl.DataFrame:
        """Read a bounded sample spread across the collection."""
        total = self.lance_db.count_entries(self.config.table) or 0

        if total <= SAMPLE_SIZE:
            return self._read_chunk(0, SAMPLE_SIZE)

        chunk = max(SAMPLE_SIZE // SAMPLE_CHUNKS, 1)
        stride = total // SAMPLE_CHUNKS
        frames = [
            self._read_chunk(i * stride, chunk) for i in range(SAMPLE_CHUNKS)
        ]
        populated = [f for f in frames if not f.is_empty()]
        return pl.concat(populated) if populated else pl.DataFrame()

    def _flatten(self, frame: pl.DataFrame, column: str) -> np.ndarray:
        """Pool every scalar component of an embedding column into one array."""
        return np.asarray(frame[column].to_list(), dtype=np.float32).ravel()

    def get_distributions(self) -> list[dict] | None:
        """Return per-model value distributions, or None when unavailable."""
        global _CACHE

        with _CACHE_LOCK:
            if _CACHE is not None:
                logger.info("Returning cached embedding distributions.")
                return _CACHE

            try:
                frame = self._read_sample()
            except Exception as e:
                logger.error(
                    f"Error reading embeddings from '{self.config.table}': {e}",
                    exc_info=True,
                )
                return None

            if frame.is_empty():
                logger.warning(
                    f"No embeddings found in collection '{self.config.table}'."
                )
                return None

            distributions = [
                _summarize(
                    "CLIP",
                    get_clip_ndims(),
                    frame.height,
                    self._flatten(frame, CLIP_COLUMN),
                ),
                _summarize(
                    "UNICOM",
                    get_unicom_ndims(),
                    frame.height,
                    self._flatten(frame, UNICOM_COLUMN),
                ),
            ]
            logger.info(
                f"Computed embedding distributions from {frame.height} images."
            )
            _CACHE = distributions
            return distributions
