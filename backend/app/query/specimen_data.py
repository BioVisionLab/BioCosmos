from openai import BaseModel

from ..services.umap import SpeciesImageUmap
from ..services.images import ImageSummary
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


class SpecimenDataPayload(BaseModel):
    species: str
    imageCounts: int

    @classmethod
    def from_data(
        cls,
        species: str,
        image_counts: int,
    ) -> "SpecimenDataPayload":
        return cls(
            species=species,
            imageCounts=image_counts,
        )


class SpecimenData:
    def __init__(self, request: Request):
        self.lance_db = request.app.state.lance_db

    def summarize(self, species: str) -> dict | None:
        try:
            image_counts = ImageSummary(
                lance_db=self.lance_db
            ).get_count(species)
            if image_counts is None:
                return None
            payload = SpecimenDataPayload.from_data(
                species=species,
                image_counts=image_counts,
            )
            return payload.model_dump()
        except Exception as e:
            logger.error(
                f"Error fetching specimen data: {e}", exc_info=True
            )
            return None


class SpeciesUmap:
    def __init__(self, request: Request):
        self.duckdb = request.app.state.duck_db

    def get_umap_embeddings(self, species: str) -> dict | None:
        try:
            umap_data: dict = SpeciesImageUmap(
                duckdb=self.duckdb
            ).get_embeddings(species)
            return umap_data
        except Exception as e:
            logger.error(
                f"Error fetching UMAP embeddings for species '{species}': {e}",
                exc_info=True,
            )
            return None
