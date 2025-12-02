from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from ..query.taxon_data import TaxonSearch

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get(
    "/search/taxon",
    tags=["Conventional Search"],
)
async def get_taxon_classification(
    request: Request, q: str, limit: int = 50
):
    """Endpoint for conventional database search.

    Expects a query parameter 'q' for the taxon to search.
    The taxon name can be a full species, genus, or higher-level taxon.
    Returns the taxon classification information from the database.
    Args:
        q (str): The taxon name to search for.
        limit (int, optional): The maximum number of results to return. Defaults to 50.
    """
    # Placeholder implementation
    logger.info(
        f"Searching database for taxon: {q} with limit {limit}"
    )
    if not q or q.strip() == "":
        logger.warning("Empty taxon search query received")
        return JSONResponse(
            content={
                "error": "Query parameter 'q' is required and cannot be empty."
            },
            status_code=400,
        )
    try:
        taxon_data = await TaxonSearch(
            request=request, query=q.strip().lower()
        ).get_classification()
        if not taxon_data:
            message = f"No classification data found for taxon: {q}"
            logger.info(message)
            return JSONResponse(
                content={"message": message},
                status_code=404,
            )
        results = taxon_data[:limit]
        logger.info(
            f"Found {len(results)} classification results for taxon: {q}"
        )
        return JSONResponse(
            content={"results": results}, status_code=200
        )
    except Exception as e:
        logger.error(
            f"Error searching for taxon classification: {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "message": f"An error occurred while searching for taxon classification: {str(e)}"
            },
            status_code=500,
        )
