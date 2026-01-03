from openai import BaseModel

from ..services.image_meta import ImageMetaService
from ..services.images import ImagePersistData
from ..services.umap import SpeciesImageUmap
from fastapi import Request
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
        self.duckdb = request.app.state.duckdb
        self.lance_db = request.app.state.lance_db

    def summarize(self, species: str) -> dict | None:
        try:
            # Get metadata count from DuckDB (total known images)
            meta_count = ImageMetaService(duckdb=self.duckdb).get_image_count_by_species(species)

            # Prefer counting only images actually ingested into LanceDB to match what is displayable
            try:
                persisted = ImagePersistData(lance_db=self.lance_db, duckdb=self.duckdb).fetch_image_ids(species)
                if isinstance(persisted, dict):
                    available_ids = persisted.get("imageIds", [])
                else:
                    available_ids = persisted or []
                image_counts = len(available_ids)
            except Exception:
                # On error, fall back to metadata count
                image_counts = meta_count if meta_count is not None else 0

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
        self.duckdb = request.app.state.duckdb

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
