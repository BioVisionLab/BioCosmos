import base64
import logging
from unittest.mock import Base

from pydantic import BaseModel
from ..services.images import ImagePersistData

logger = logging.getLogger(__name__)


class SearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]

    @classmethod
    def from_data(cls, query: str, resuls: list[dict]):
        """ """
        return cls(query=query, results=resuls)


class TextToImageSearch:
    """
    A class to handle image search operations.
    """

    def __init__(self, query: str = "", limit: int = 50):
        """
        Initialize the TextToImageSearch class.
        """
        self.query = query.strip().lower()
        self.limit = limit

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
        search_img = ImagePersistData()
        results = search_img.fetch_similar_images_from_text(
            self.query, limit=self.limit
        )
        return results


class ImageToImageSearch:
    """
    A class to handle image to image search operations.
    """

    def __init__(self, query: str = "", limit: int = 50):
        """
        Initialize the ImageToImageSearch class.
        The query is base64 encoded image string.
        """
        self.query = query.strip()
        self.limit = limit

    def search(self) -> list[dict] | None:
        """
        Perform an image to image search.
        """
        if not self.query:
            logger.warning(
                "Empty query provided for image to image search."
            )
            return None
        # Placeholder for actual search logic
        logger.info("Performing image to image search for query.")
        if "," in self.query:
            _, encoded = self.query.split(",", 1)
        else:
            encoded = self.query
        query_img: bytes = base64.b64decode(encoded)
        search_img = ImagePersistData()
        results = search_img.fetch_similar_images_from_bytes(
            query_img, limit=self.limit
        )
        return results
