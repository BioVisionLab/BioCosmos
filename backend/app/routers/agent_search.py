"""
Agent-based semantic search router.
Uses OpenAI function calling to intelligently query multiple data sources.
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..query.agent_query import TextToAgent


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search/agent", tags=["ML Search"])
async def agent_search(request: Request, q: str):
    """
    Agent-based semantic search endpoint.

    Uses OpenAI function calling to intelligently break down complex queries
    and query multiple data sources (image similarity, location, traits, colors).

    Args:
        q: Natural language search query

    Returns:
        200: { query, total, results: [{ imgId, species, score, tool_names }] }
        400: { error } ? empty or missing query
        500: { error } ? internal failure

    Example queries:
    - "blue butterflies in Brazil"
    - "species similar to Danaus plexippus in tropical regions"
    - "red butterflies with high canopy affinity from South America"
    """
    query = q.strip()

    if not query:
        return JSONResponse(
            content={"error": "Query parameter 'q' is required and cannot be empty."},
            status_code=400,
        )

    try:
        logger.info(f"Received agent search query: {query}")

        agent_service = TextToAgent(request=request, query=query)
        results = await agent_service.get_results()

        if not results:
            logger.warning(f"No results found for query: {query}")
            return JSONResponse(
                content={
                    "query": query,
                    "total": 0,
                    "results": [],
                    "message": "No species found matching the criteria.",
                },
                status_code=200,
            )

        return JSONResponse(
            content={
                "query": query,
                "total": len(results),
                "results": results,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(
            f"Agent search failed for query '{query}': {e}",
            exc_info=True,  # Logs full traceback server-side
        )
        return JSONResponse(
            content={"error": "An internal error occurred. Please try again later."},
            status_code=500,
        )
