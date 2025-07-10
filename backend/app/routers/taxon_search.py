# Query taxonomy data based on the species name
# Use GBIF Species Search API to find species taxonomy data
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging
from ..searches.taxon import TaxonSearch

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/taxon")
async def search_taxon(q: str):
    """
    Search for species taxonomy data using the GBIF (Global Biodiversity Information Facility) API.

    Args:
        q (str): The species name to search for.

    Returns:
        JSONResponse: A JSON response containing the species taxonomy data or an error message.
    """
    logger.info("Received taxon search request")
    q = q.strip().lower() if q else None
    if q is None or q == "":
        logger.warning("Taxon search query is empty")
        return JSONResponse(
            content={
                "message": "Query parameter 'q' is required and cannot be empty."
            },
            status_code=400,
        )
    logger.info(f"Searching for taxon: {q}")
    try:
        taxon_data = await TaxonSearch(query=q).search()
        if taxon_data is None:
            message = f"No data found for species: {q}"
            logger.info(message)
            return JSONResponse(
                content={"message": message},
                status_code=404,
            )
        logger.info(f"Taxon data found for: {q}")
        logger.info(f"Taxon data: {taxon_data}")
        return JSONResponse(content=taxon_data, status_code=200)
    except Exception as e:
        logger.error(f"Error searching for taxon: {e}", exc_info=True)
        return JSONResponse(
            content={
                "message": f"An error occurred while searching for taxon: {str(e)}"
            },
            status_code=500,
        )
