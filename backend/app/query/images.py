import base64
import logging
import re

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
        self, request: Request, query: str = "", limit: int = 50
    ):
        """
        Initialize the TextToImageSearch class.
        """
        self.request = request
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
        search_img = ImagePersistData(
            lance_db=self.request.app.state.lance_db
        )
        results = search_img.fetch_similar_images_from_text(
            self.request, self.query, limit=self.limit
        )
        return results


class ImageToImageSearch:
    """
    A class to handle image to image search operations.
    """

    def __init__(
        self, request: Request, query: str = "", limit: int = 50
    ):
        """
        Initialize the ImageToImageSearch class.
        The query is base64 encoded image string.
        """
        self.request = request
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
        search_img = ImagePersistData(
            lance_db=self.request.app.state.lance_db
        )
        results = search_img.fetch_similar_images_from_bytes(
            request=self.request,
            image_bytes=query_img,
            limit=self.limit,
        )
        return results
