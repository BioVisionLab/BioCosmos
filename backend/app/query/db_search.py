from pydantic import BaseModel
from fastapi import Request
import logging

from ..services.image_meta import ImageMetaService

from ..services.gbif import GbifPersistData, SearchGbifData

logger = logging.getLogger(__name__)


class DbSearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]

    @classmethod
    def from_data(cls, query: str, results: list[dict]):
        """ """
        return cls(query=query, results=results)

    @classmethod
    def empty(cls, query: str):
        """ """
        return cls(query=query, results=[])


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
        results: list[SearchGbifData] = search_db.search_any(self.query, self.limit)

        if not results:
            logger.info(f"No results found for query: {self.query}")
            return DbSearchPayload.empty(query=self.query).model_dump()
        filtered_results = self.remove_list_not_in_meta(results)
        if not filtered_results:
            logger.info(f"No results found in metadata for query: {self.query}")
            return DbSearchPayload.empty(query=self.query).model_dump()
        logger.info(f"Found {len(filtered_results)} results for query: {self.query}")
        return DbSearchPayload.from_data(
            query=self.query, results=[r.model_dump() for r in filtered_results]
        ).model_dump()

    def remove_list_not_in_meta(
        self, result: list[SearchGbifData]
    ) -> list[SearchGbifData]:
        """ """
        existing_species = ImageMetaService(
            duckdb=self.request.app.state.duck_db
        ).check_species_exists([r.species for r in result])
        filtered_results = [r for r in result if r.species in existing_species]
        logger.info(
            f"Filtered search results to {len(filtered_results)} species that exist in image metadata."
        )
        return filtered_results
