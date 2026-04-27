import logging
import os

from fastapi import Request

from ..configs.config import ImageConfig
from ..services.images import ImagePersistData
from ..services.metadata import ImageMetaService

logger = logging.getLogger(__name__)


class ImageMetaRetrieval:
    """
    A class to handle image retrieval operations.
    This class retrieves image metadata from the database.
    """

    def __init__(self, request: Request):
        """
        Initialize the ImageMetaRetrieval class.
        """
        self.duckdb = request.app.state.duck_db
        self.lance_db = request.app.state.lance_db

    def get_species_image_ids(self, scientific_name: str) -> list[str]:
        """
        Retrieve image IDs associated with a species.
        """
        image_ids: list[str] = ImageMetaService(
            duckdb=self.duckdb
        ).get_image_ids_by_species(scientific_name)
        return image_ids

    def get_meta_by_id(self, image_id: str) -> dict | None:
        """
        Retrieve metadata for a single image ID.

        Returns a dict of metadata fields if found, otherwise None.
        """
        try:
            df = ImageMetaService(duckdb=self.duckdb).get_meta_by_image_id(image_id)
            if df is None or df.is_empty():
                return None
            rows = df.to_dicts()
            if not rows:
                return None
            row = rows[0]
            # Only return a minimal set of fields to avoid exposing internal data
            allowed = ["license", "uuid", "uri", "class_dv", "lat", "lon", "source_db"]
            filtered = {k: row.get(k) for k in allowed if k in row}
            return filtered
        except Exception as e:
            logger.error(f"Error fetching metadata for image id {image_id}: {e}")
            return None


class ImageFileRetrieval:
    """
    Retrieves images from disk. Both full-resolution images and thumbnails
    are pre-generated during ingestion. Paths and formats are driven by config.yaml.
    """

    def __init__(self, request: Request):
        self.lance_db = request.app.state.lance_db
        self.duckdb = request.app.state.duck_db
        config = ImageConfig()
        self.file_format = config.format
        self.processed_dir = config.processed_dir
        self.thumbnail_dir = config.thumbnail_dir

    def get_species_thumbnail(self, scientific_name: str) -> str | None:
        """Retrieve the thumbnail image file path for a species."""
        img_id: str | None = ImageMetaService(
            duckdb=self.duckdb
        ).get_species_main_image_id(scientific_name)
        if img_id is None:
            return None
        return self.get_thumbnail(img_id)

    def get_species_image(self, scientific_name: str) -> str | None:
        """Retrieve the full-resolution image file path for a species."""
        return ImagePersistData(
            lance_db=self.lance_db, duckdb=self.duckdb
        ).fetch_image_path(scientific_name)

    def get_thumbnail(self, image_id: str) -> str | None:
        """Retrieve the pre-generated thumbnail file path."""
        thumbnail_path = self._get_thumbnail_path(image_id)
        if os.path.exists(thumbnail_path):
            return thumbnail_path
        logger.warning(f"Thumbnail not found on disk: {thumbnail_path}")
        return None

    def get_full_res(self, image_id: str) -> str | None:
        """Retrieve the full-resolution image file path."""
        static_path = self._get_image_path(image_id)
        if os.path.exists(static_path):
            return static_path

        # Fall back to the path stored in LanceDB
        img_path = ImagePersistData(
            lance_db=self.lance_db,
            duckdb=self.duckdb,
        ).get_img_path_by_id(image_id)
        if img_path is not None and os.path.exists(img_path):
            return img_path

        return None

    def _get_image_path(self, image_id: str) -> str:
        return os.path.join(
            self.processed_dir,
            f"{image_id}.{self.file_format}",
        )

    def _get_thumbnail_path(self, image_id: str) -> str:
        return os.path.join(
            self.thumbnail_dir,
            f"{image_id}_thumbnail.{self.file_format}",
        )
