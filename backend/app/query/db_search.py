from pydantic import BaseModel
from fastapi import Request
import logging

from ..services.gbif import GbifPersistData

logger = logging.getLogger(__name__)


class DbSearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]

    @classmethod
    def from_data(cls, query: str, results: list[dict]):
        """ """
        return cls(query=query, results=results)


class TextToDbSearch:
    """
    A class to handle text to database search operations.
    """

    def __init__(
        self,
        request: Request,
        query: str = "",
        limit: int = 50,
    ):
        """
        Initialize the TextToDbSearch class.
        """
        self.request = request
        self.query = query.strip().lower()
        self.limit = limit

    def search(self) -> dict | None:
        """
        Perform a text to database search.
        """
        if not self.query:
            logger.warning("Empty query provided for text to database search.")
            return None
        # Placeholder for actual search logic
        logger.info(f"Performing text to database search for query: {self.query}")
        search_db = GbifPersistData(self.request.app.state.duck_db)
        results = search_db.search_any(self.query, self.limit)
        if not results:
            logger.info(f"No results found for query: {self.query}")
            return None
        logger.info(f"Found {len(results)} results for query: {self.query}")
        return DbSearchPayload.from_data(
            query=self.query, results=[r.model_dump() for r in results]
        ).model_dump()
