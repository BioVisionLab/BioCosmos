"""
Agent-based semantic search router.
Uses OpenAI function calling to intelligently query multiple data sources.
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..services.agent import AgentSearchService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search/agent", tags=["ML Search"])
async def agent_search(request: Request, q: str):
    """
    Agent-based semantic search endpoint.

    Uses OpenAI function calling to intelligently break down complex queries
    and query multiple data sources (image similarity, location, traits, colors).

    Example queries:
    - "which species of butterfly looks like monarch and lives in ecuador and has red colors and lives in the canopy"
    - "find butterflies similar to danaus plexippus that live in tropical regions"
    - "show me red butterflies with high canopy affinity from south america"
    """
    query = q.strip()

    if not query:
        return JSONResponse(
            content={
                "error": "Query parameter is required and cannot be empty."
            },
            status_code=400,
        )

    try:
        logger.info(f"Received agent search query: {query}")
        agent_service = AgentSearchService(request=request)
        results = await agent_service.search(query)

        if not results.top_results and not results.other_results:
            logger.warning(f"No results found for query: {query}")
            return JSONResponse(
                content={
                    "query": query,
                    "results": [],
                    "message": "No species found matching the criteria.",
                },
                status_code=200,
            )

        return JSONResponse(
            content=results.model_dump(by_alias=True),
            status_code=200,
        )

    except Exception as e:
        logger.error(
            f"Error during agent search for query '{query}': {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "error": f"An internal error occurred during agent search: {str(e)}"
            },
            status_code=500,
        )
