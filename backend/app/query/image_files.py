from io import BytesIO
import os
from ..database.model import LanceSchema
from fastapi import Request
from PIL import Image
from ..services.images import ImagePersistData

STATIC_PATH = "static/"


class ImageFileRetrieval:
    """
    A class to handle image retrieval operations.
    Return file path to static image.
    """

    def __init__(self, request: Request):
        """
        Initialize the ImageRetrieval class.
        """
        self.lance_db = request.app.state.lance_db
        self.file_format = "webp"

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
            lance_db=self.lance_db
        ).get_img_by_id(image_id)
        return img_bytes

    def _write_to_file(self, path, img_bytes: bytes) -> None:
        """
        Write image bytes to a static file.
        """
        Image.open(BytesIO(img_bytes)).save(
            path, format=self.file_format.upper()
        )

    def _write_thumbnail_to_file(
        self, path, img_bytes: bytes
    ) -> None:
        """
        Write thumbnail image bytes to a static file.
        """
        img = Image.open(BytesIO(img_bytes))
        img.thumbnail((128, 128), resample=Image.LANCZOS)
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
