from io import BytesIO
import os
from fastapi import Request
from PIL import Image

from ..services.image_meta import ImageMetaService
from ..services.images import ImagePersistData

STATIC_PATH = "static/"
THUMBNAIL_MAX_RESOLUTION = 128
FULL_RES_MAX_RESOLUTION = 800


class ImageMetaRetrieval:
    """
    A class to handle image retrieval operations.
    This class retrieves image metadata from the database.
    """

    def __init__(self, request: Request):
        """
        Initialize the ImageMetaRetrieval class.
        """
        self.duck_db = request.app.state.duck_db
        self.lance_db = request.app.state.lance_db

    def get_species_image_ids(
        self, scientific_name: str
    ) -> list[str]:
        """
        Retrieve image IDs associated with a species.
        """
        image_ids: list[str] = ImageMetaService(
            duckdb=self.duck_db
        ).get_image_ids_by_species(scientific_name)
        return image_ids


class ImageFileRetrieval:
    """
    A class to handle image retrieval operations.
    This class retrieves images from the LanceDB database,
    saves them as static files if they don't already exist,
    and provides paths to these static files.
    Attributes:
        lance_db: The LanceDB database instance.
        file_format: The image file format to use (e.g., "webp").
    Methods:
        get_thumbnail(image_id): Retrieve the thumbnail image file path.
        get_full_res(image_id): Retrieve the full-resolution image file path.

    Maximum resolutions:
        - Thumbnail: 128 pixels
        - Full-resolution: 400 pixels
    """

    def __init__(self, request: Request):
        """
        Initialize the ImageRetrieval class.
        """
        self.lance_db = request.app.state.lance_db
        self.duck_db = request.app.state.duck_db
        self.file_format = "webp"

    def get_species_thumbnail(
        self, scientific_name: str
    ) -> str | None:
        """
        Retrieve the thumbnail image file path for a species.
        """
        image_ids: list[str] = ImageMetaService(
            duckdb=self.duck_db
        ).get_image_ids_by_species(scientific_name)

        if not image_ids:
            return None

        # For simplicity, use the first image ID for the thumbnail
        first_image_id = image_ids[0]
        return self.get_thumbnail(first_image_id)

    def get_species_image(self, scientific_name: str) -> str | None:
        """
        Retrieve the full-resolution image file path for a species.
        """
        image_ids: list[str] = ImageMetaService(
            duckdb=self.duck_db
        ).get_image_ids_by_species(scientific_name)

        if not image_ids:
            return None

        # For simplicity, use the first image ID for the full-resolution image
        first_image_id = image_ids[0]
        return self.get_full_res(first_image_id)

    def get_thumbnail(self, image_id: str) -> str | None:
        """
        Retrieve the thumbnail image file path.
        """
        static_path = self._get_static_thumbnail_path(image_id)
        if os.path.exists(static_path):
            return static_path

        img_bytes = self._get_image_by_id(image_id)
        if img_bytes is None:
            return None

        os.makedirs(os.path.dirname(static_path), exist_ok=True)
        self._write_thumbnail_to_file(static_path, img_bytes)
        return static_path

    def get_full_res(self, image_id: str) -> str | None:
        """
        Retrieve the full-resolution image file path.
        """
        static_path = self._get_static_image_path(image_id)
        if os.path.exists(static_path):
            return static_path

        img_bytes = self._get_image_by_id(image_id)
        if img_bytes is None:
            return None

        os.makedirs(os.path.dirname(static_path), exist_ok=True)
        self._write_to_file(static_path, img_bytes)
        return static_path

    def _get_image_by_id(self, image_id: str) -> bytes | None:
        """
        Retrieve an image by its ID.
        """
        img_bytes: bytes = ImagePersistData(
            lance_db=self.lance_db,
            duckdb=self.duck_db,
        ).get_img_by_id(image_id)
        return img_bytes

    def _write_to_file(
        self,
        path,
        img_bytes: bytes,
        max_resolution: int = FULL_RES_MAX_RESOLUTION,
    ) -> None:
        """
        Write image bytes to a static file.
        Resize the image if it exceeds max_resolution.
        """
        img = Image.open(BytesIO(img_bytes))
        if max(img.size) > max_resolution:
            img.thumbnail(
                (max_resolution, max_resolution),
                resample=Image.LANCZOS,
            )
        img.save(path, format=self.file_format.upper())

    def _write_thumbnail_to_file(
        self,
        path,
        img_bytes: bytes,
        max_resolution: int = THUMBNAIL_MAX_RESOLUTION,
    ) -> None:
        """
        Write thumbnail image bytes to a static file.
        Resize the thumbnail if it exceeds 128 pixels.
        """
        img = Image.open(BytesIO(img_bytes))
        if max(img.size) > max_resolution:
            img.thumbnail(
                (max_resolution, max_resolution),
                resample=Image.LANCZOS,
            )
        img.save(path, format=self.file_format.upper())

    def _get_static_image_path(self, image_id: str) -> str:
        """
        Get the static file path for an image.
        """
        return os.path.join(
            STATIC_PATH,
            self.file_format,
            f"{image_id}.{self.file_format}",
        )

    def _get_static_thumbnail_path(self, image_id: str) -> str:
        """
        Get the static file path for a thumbnail image.
        """
        return os.path.join(
            STATIC_PATH,
            self.file_format,
            "thumbnails",
            f"{image_id}_thumbnail.{self.file_format}",
        )
