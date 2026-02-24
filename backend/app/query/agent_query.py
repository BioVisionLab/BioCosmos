from fastapi import Request
from typing import List
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


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

    def get_results(self):
        # Placeholder for the actual agent search logic
        # This would involve calling the AgentSearchService and processing results
        return {
            "message": "This is a placeholder for agent search results."
        }
