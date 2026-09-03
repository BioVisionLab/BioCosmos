import logging

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..services.embedding_stats import EmbeddingStatsService

logger = logging.getLogger(__name__)


class EmbeddingSummary(BaseModel):
    """Five-number summary of one model's embedding component values."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # `embedding_model` would otherwise collide with Pydantic's
        # protected `model_` namespace.
        protected_namespaces=(),
    )

    embedding_model: str
    dimensions: int
    image_count: int
    sample_size: int
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float
    lower_whisker: float
    upper_whisker: float
    mean: float
    std_dev: float


class EmbeddingStatsPayload(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    distributions: list[EmbeddingSummary]


class EmbeddingDistribution:
    def __init__(self, request: Request):
        self.lance_db = request.app.state.lance_db

    def get_distributions(self) -> dict | None:
        """Summarize CLIP and UNICOM embedding value distributions."""
        try:
            distributions = EmbeddingStatsService(
                lance_db=self.lance_db
            ).get_distributions()
            if distributions is None:
                return None
            payload = EmbeddingStatsPayload(distributions=distributions)
            return payload.model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Error fetching embedding distributions: {e}", exc_info=True
            )
            return None
