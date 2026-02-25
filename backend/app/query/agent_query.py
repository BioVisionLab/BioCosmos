from fastapi import Request
from typing import List
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..services.agent import AgentSearchService


class AgentSearchPayload(BaseModel):
    """
    Complete search response payload containing ranked results.

    Attributes:
        query: Original user query string
        top_results: High-confidence results (score >= threshold, typically 0.3)
                     Sorted by score in descending order
        other_results: Lower-confidence results (score < threshold)
                       Sorted by score in descending order
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    query: str
    combined: List[dict]
    location: List[dict]
    traits: List[dict]
    similarity: List[dict]


class TextToAgent:
    def __init__(self, request: Request, query: str):
        self.request = request
        self.query = query

    def get_results(self) -> dict:
        agent_service = AgentSearchService(request=self.request)
        results = agent_service.search(query=self.query)
        # Get multitool results and filter out overlaps
        # aggregated = agent_service._aggregate_multitool_results(
        #     results
        # )
        return results.to_dict(by_alias=True)

    # def _aggregate_multitool_results(self, results) -> List[dict]:
    #     """
    #     Combine results from multiple tools into a single list, removing duplicates.

    #     Args:
    #         results: The raw results from the agent search service.
    #     Returns:
    #         A list of unique results with combined information from all tools.
    #     """
