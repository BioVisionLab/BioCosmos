from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from fastapi import Request
import polars as pl
import logging

from ..services.image_meta import ImageMetaService
from ..services.images import ImagePersistData

logger = logging.getLogger(__name__)


class VisuallySimilarSpeciesPayload(BaseModel):
    """
    A class to represent visually similar species data.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    all_morphotypes: list[dict]
    dorsal: list[dict]
    ventral: list[dict]


class SpeciesSimilarity:
    """
    A class to handle species similarity search operations.
    """

    def __init__(self, request: Request, limit: int = 20):
        """
        Initialize the SpeciesSimilarity class.
        Args:
            request (Request): The FastAPI request object.
        """
        self.lance_db = request.app.state.lance_db
        self.duck_db = request.app.state.duck_db
        self.limit = limit

    def find_similar_species(self, species_name: str) -> dict | None:
        """
        Find species similar to the given species name using image similarity.

        Args:
            species_name (str): The species name to find similar species for.
            limit (int): The maximum number of similar species to return.

        Returns:
            list[LanceSchema] | None: A
            list of dicts with keys: imgId, species, distance (smaller = more similar),
            or None if no similar species were found.
        similar_images: list[dict] = (
                ImagePersistData(
                    lance_db=self.request.app.state.lance_db
                ).find_similar_images(
                    species_name=species_name,
                    limit=limit,
                )
                or []
            )
        """
        # Get image ID for the species
        try:
            image_ids = self._get_image_ids_for_species(species_name)
            if image_ids is None:
                logger.info(
                    f"No image IDs found for species: {species_name}"
                )
                return None
            all_morphotypes: pl.DataFrame = self._get_similar_images(
                species_name=species_name,
                image_ids=image_ids,
            )
            dorsal: pl.DataFrame | None = (
                self._get_similar_images_by_side(
                    similar_images=all_morphotypes,
                    species_name=species_name,
                    side="dorsal",
                )
            )
            ventral: pl.DataFrame | None = (
                self._get_similar_images_by_side(
                    similar_images=all_morphotypes,
                    species_name=species_name,
                    side="ventral",
                )
            )
            payload = VisuallySimilarSpeciesPayload(
                all_morphotypes=all_morphotypes.to_dicts()
                if all_morphotypes
                else [],
                dorsal=dorsal.to_dicts() if dorsal else [],
                ventral=ventral.to_dicts() if ventral else [],
            )
            return payload.model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return []

    def _get_similar_images(
        self, species_name: str, image_ids: list[str]
    ) -> pl.DataFrame | None:
        try:
            similar_images: pl.DataFrame = ImagePersistData(
                lance_db=self.lance_db,
                duckdb=self.duck_db,
            ).find_similar_images(
                image_ids=image_ids,
                limit=self.limit,
            )
            if similar_images is None or len(similar_images) == 0:
                logger.info("No similar images found.")
                return None
            return self._filter_similar_images(
                similar_images, species_name
            )
        except Exception as e:
            logger.error(
                f"Error retrieving similar images: {e}",
                exc_info=True,
            )
            return None

    def _get_similar_images_by_side(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
        side: str,
    ) -> pl.DataFrame | None:
        try:
            dorsal_images = self._filter_by_side(
                similar_images, side=side
            )
            if dorsal_images is None or len(dorsal_images) == 0:
                logger.info("No dorsal similar images found.")
                return None
            similar_images = self._get_similar_images(
                species_name=species_name,
                image_ids=dorsal_images,
            )
            return self._filter_similar_images(
                similar_images, species_name
            )
        except Exception as e:
            logger.error(
                f"Error retrieving dorsal similar images: {e}",
                exc_info=True,
            )
            return None

    def _filter_similar_images(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
    ) -> pl.DataFrame:
        """
        Filter out images that belong to the same species as the query species.

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
            species_name (str): The species name to filter out.
        Returns:
            pl.DataFrame: Filtered DataFrame with images not belonging to the query species.
        """
        filtered_images = similar_images.filter(
            pl.col("species").str.to_lowercase().replace(" ", "_")
            != species_name.lower().replace(" ", "_")
        )
        return filtered_images

    def _get_image_ids_for_species(
        self, species_name: str
    ) -> list[str] | None:
        try:
            meta_service = ImageMetaService(duckdb=self.duck_db)
            image_meta = meta_service.get_image_meta_by_species(
                species=species_name
            )
            if image_meta is None or len(image_meta) == 0:
                logger.info(
                    f"No images found for species: {species_name}"
                )
                return None
            # Need to remove .png extension if present
            return [
                meta.img_id.removesuffix(".png")
                for meta in image_meta
            ]
        except Exception as e:
            logger.error(
                f"Error fetching image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return None

    def _filter_by_side(
        self, similar_images: pl.DataFrame, side: str
    ) -> list[str] | None:
        """
        Filter similar images to only include dorsal views.

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
        Returns:
            list[str] | None: List of dorsal image IDs or None if none found.
        """
        filtered_images = similar_images.filter(
            pl.col("class_dv").str.to_lowercase() == side.lower()
        )
        if filtered_images is None or len(filtered_images) == 0:
            logger.info(f"No {side} images found in similar images.")
            return None
        return (
            filtered_images.select(pl.col("imgId"))
            .to_series()
            .to_list()
        )
