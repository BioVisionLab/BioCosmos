import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..query.db_search import TextToDbSearch

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get(
    "/search/db",
    tags=["Conventional Search"],
)
async def search_db(request: Request, q: str, limit: int = 50):
    """Endpoint for conventional database search.

    Expects a query parameter 'q' for the taxon to search.
    The taxon name can be a full species, genus, or higher-level taxon.
    Returns the taxon classification information from the database.
    Args:
        q (str): The taxon name to search for.
        limit (int, optional): The maximum number of results to return. Defaults to 50.
    """
    # Placeholder implementation
    logger.info(f"Searching database for taxon: {q} with limit {limit}")
    if not q or q.strip() == "":
        logger.warning("Empty taxon search query received")
        return JSONResponse(
            content={"error": "Query parameter 'q' is required and cannot be empty."},
            status_code=400,
        )
    try:
        search_results = TextToDbSearch(request=request, query=q, limit=limit).search()
        if not search_results:
            message = f"No data found for taxon: {q}"
            logger.info(message)
            return JSONResponse(
                content={"message": message},
                status_code=404,
            )
        logger.info(f"Found {len(search_results)} results for taxon: {q}")
        return JSONResponse(content=search_results, status_code=200)
    except Exception as e:
        logger.error(
            f"Error searching for taxon: {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "message": f"An error occurred while searching for taxon: {str(e)}"
            },
            status_code=500,
        )
