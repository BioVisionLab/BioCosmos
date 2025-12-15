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

    any_sides: list[dict]
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
            dict | None: A dictionary containing similar species data or None if not found.
        """
        # Get image ID for the species
        try:
            image_ids = self._get_image_ids_for_species(species_name)
            if image_ids is None or image_ids.is_empty():
                logger.info(
                    f"No image IDs found for species: {species_name}"
                )
                return None
            any_sides: list[dict] = (
                self._get_similar_images_all_morphotypes(
                    species_images=image_ids,
                    species_name=species_name,
                )
            )
            dorsal: list[dict] = self._get_similar_images_by_side(
                species_images=image_ids,
                species_name=species_name,
                side="dorsal",
            )
            ventral: list[dict] = self._get_similar_images_by_side(
                species_images=image_ids,
                species_name=species_name,
                side="ventral",
            )
            payload = VisuallySimilarSpeciesPayload(
                any_sides=any_sides,
                dorsal=dorsal,
                ventral=ventral,
            )
            return payload.model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return None

    def _get_similar_images(
        self, species_name: str, image_ids: list[str]
    ) -> list[dict]:
        try:
            similar_images: pl.DataFrame = ImagePersistData(
                lance_db=self.lance_db,
                duckdb=self.duck_db,
            ).find_similar_images(
                image_ids=image_ids,
                limit=self.limit,
            )
            if similar_images is None or similar_images.is_empty():
                logger.info("No similar images found.")
                return []
            return self._filter_similar_images(
                similar_images, species_name
            )
        except Exception as e:
            logger.error(
                f"Error retrieving similar images: {e}",
                exc_info=True,
            )
            return []

    def _get_similar_images_all_morphotypes(
        self,
        species_images: pl.DataFrame,
        species_name: str,
    ) -> list[dict]:
        try:
            image_ids = self._get_image_ids(species_images)
            similar_images = self._get_similar_images(
                species_name=species_name,
                image_ids=image_ids,
            )
            return similar_images
        except Exception as e:
            logger.error(
                f"Error retrieving all morphotype similar images: {e}",
                exc_info=True,
            )
            return []

    def _get_similar_images_by_side(
        self,
        species_images: pl.DataFrame,
        species_name: str,
        side: str,
    ) -> list[dict]:
        try:
            side_images: list[str] | None = self._filter_by_side(
                species_images, side=side
            )
            if side_images is None or len(side_images) == 0:
                logger.info(f"No {side} similar images found.")
                return []
            similar_images = self._get_similar_images(
                species_name=species_name,
                image_ids=side_images,
            )
            return similar_images
        except Exception as e:
            logger.error(
                f"Error retrieving {side} similar images: {e}",
                exc_info=True,
            )
            return []

    def _filter_similar_images(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
    ) -> list[dict]:
        """
        Filter out images that belong to the same species as the query species.

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
            species_name (str): The species name to filter out.
        Returns:
            list[dict]: List of similar images not belonging to the query species.
        """
        filtered_images = similar_images.filter(
            pl.col("species")
            .str.to_lowercase()
            .str.replace_all(" ", "_", literal=True)
            != species_name.lower().replace(" ", "_")
        )
        if filtered_images is None or filtered_images.is_empty():
            logger.info(
                f"No similar images found for species different than: {species_name}"
            )
            return []
        return filtered_images.to_dicts()

    def _get_image_ids_for_species(
        self, species_name: str
    ) -> pl.DataFrame | None:
        """
        Get image IDs for a given species.
        Args:
            species_name (str): The species name to get image IDs for.
        Returns:
            pl.DataFrame | None: DataFrame containing image IDs or None if not found.
        """
        try:
            meta_service = ImageMetaService(duckdb=self.duck_db)
            image_meta: pl.DataFrame | None = (
                meta_service.get_image_meta_by_species(
                    species=species_name
                )
            )
            if image_meta is None or image_meta.is_empty():
                logger.info(
                    f"No images found for species: {species_name}"
                )
                return None
            # Need to remove .png extension if present
            return image_meta
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
        Filter similar images by side (dorsal or ventral).

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
        Returns:
            list[str] | None: List of dorsal image IDs or None if none found.
        """
        filtered_images = similar_images.filter(
            pl.col("class_dv").str.to_lowercase() == side.lower()
        )
        if filtered_images is None or filtered_images.is_empty():
            logger.info(f"No {side} images found in similar images.")
            return None
        return self._get_image_ids(filtered_images)

    def _get_image_ids(self, image_meta: pl.DataFrame) -> list[str]:
        """
        Extract image IDs from image metadata.

        Args:
            image_meta (pl.DataFrame): DataFrame containing image metadata.
        Returns:
            list[str]: List of image IDs.
        """
        return (
            image_meta.select(pl.col("img_id")).to_series().to_list()
        )
