import polars as pl

from typing import List
from fastapi import Request

from ..services.agent import AgentSearchService


class TextToAgent:
    """
    Thin orchestration layer between the FastAPI endpoint and AgentSearchService.

    Responsible for:
    - Instantiating AgentSearchService with the current request context
    - Awaiting the search and converting the result to a serializable format
    """

    def __init__(self, request: Request, query: str):
        self.request = request
        self.query = query

    async def get_results(self) -> List[dict]:
        """
        Run agent search and return results as a list of dicts.

        Returns:
            List of dicts with keys [imgId, species, score, tool_names],
            sorted by score descending. Returns [] if no results found.
        """
        agent_service = AgentSearchService(request=self.request)
        results: pl.DataFrame = await agent_service.search(query=self.query)

        if results.is_empty():
            return []

        return results.to_dicts()
