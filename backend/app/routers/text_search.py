from ..searches.images import TextToImageSearch

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/text-search")
async def search_text(q: str):
    """Endpoint for text to image search.

    Expects a query parameter 'q' for the search term.
    Returns a list of search results based on the text embedding.
    Args:
        q (str): The search query string.
    Returns:
        JSONResponse: A response containing the search results or an error message.
    """
    query = q.strip() if q else None

    if query is None or query == "":
        return JSONResponse(
            content={
                "error": "Query parameter 'q' is required and cannot be empty."
            },
            status_code=400,
        )
    try:
        search = TextToImageSearch(query=query)
        search_results = search.search()
        if search_results is None:
            logger.error(
                f"No search results returned from '{query}'."
            )
            return JSONResponse(
                content={
                    "error": f"No search results found for '{query}'."
                },
                status_code=500,
            )
        return JSONResponse(content=search_results, status_code=200)
    except Exception as e:
        logger.error(
            f"Error during CLIP text search for query '{query}': {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during text search."
            },
            status_code=500,
        )
