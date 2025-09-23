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

    def __init__(self, query: str = ""):
        """
        Initialize the TextToImageSearch class.
        """
        self.query = query.strip().lower()

    def search(self) -> dict | None:
        """cle
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
            self.query
        )
        return results
