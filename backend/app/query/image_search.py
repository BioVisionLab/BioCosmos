import io
import logging
from PIL import Image

from fastapi import Request
from pydantic import BaseModel
from ..services.images import ImagePersistData

logger = logging.getLogger(__name__)


class SearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]

    @classmethod
    def from_data(cls, query: str, results: list[dict]):
        """ """
        return cls(query=query, results=results)


class TextToImageSearch:
    """
    A class to handle image search operations.
    """

    def __init__(
        self,
        request: Request,
        query: str = "",
        limit: int = 50,
        max_distance: float | None = None,
    ):
        """
        Initialize the TextToImageSearch class.
        """
        self.request = request
        self.query = query.strip().lower()
        self.limit = limit
        self.max_distance = max_distance

    def search(self) -> list[dict] | None:
        """
        Perform a text to image search.
        """
        if not self.query:
            logger.warning(
                "Empty query provided for text to image search."
            )
            return None
        # Placeholder for actual search logic
        logger.info(
            f"Performing text to image search for query: {self.query}"
        )
        search_img = ImagePersistData(lance_db=self.request.app.state.lance_db,duckdb=self.request.app.state.duckdb,)
        results = search_img.fetch_similar_images_from_text(
            self.request,
            self.query,
            limit=self.limit,
            max_distance=self.max_distance,
        )
        return results


class ImageToImageSearch:
    """
    A class to handle image to image search operations.
    """

    def __init__(self, request: Request, limit: int = 50):
        """
        Initialize the ImageToImageSearch class.
        The query is base64 encoded image string.
        """
        self.request = request
        self.limit = limit

    def search(self, image_bytes: bytes) -> list[dict] | None:
        """
        Perform an image to image search.
        """
        if not image_bytes:
            logger.warning(
                "Empty query provided for image to image search."
            )
            return None
        if not self._verify_image(image_bytes):
            logger.error("Invalid image data provided for search.")
            return None
        # Placeholder for actual search logic
        logger.info("Performing image to image search for query.")

        search_img = ImagePersistData(lance_db=self.request.app.state.lance_db,duckdb=self.request.app.state.duckdb,)
        results = search_img.fetch_similar_images_from_bytes(
            request=self.request,
            image_bytes=image_bytes,
            limit=self.limit,
        )
        return results

    def _verify_image(self, image_bytes: bytes) -> bool:
        """Verify if the provided bytes represent a valid image."""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.verify()  # This will raise an exception if the image is not valid
            return True
        except (IOError, SyntaxError) as e:
            self.logger.error(
                f"Invalid image data: {e}",
                exc_info=True,
            )
            return False
