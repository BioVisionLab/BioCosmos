# Query taxonomy data based on the species name
# Use GBIF Species Search API to find species taxonomy data
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from ..query.taxon_data import TaxonSearch

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/stats/taxon", tags=["Data Statistics"])
async def get_taxon_counts(request: Request):
    """
    Get the counts of species in each taxon.
    """
    logger.info("Received taxon counts request")
    try:
        counts = TaxonSearch(request=request).get_counts()
        logger.info(f"Taxon counts found: {counts}")
        return JSONResponse(content=counts, status_code=200)
    except Exception as e:
        logger.error(
            f"Error fetching taxon counts: {e}", exc_info=True
        )
        return JSONResponse(
            content={
                "message": f"An error occurred while fetching taxon counts: {str(e)}"
            },
            status_code=500,
        )
