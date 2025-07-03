# Query taxonomy data based on the species name
# Use GBIF Species Search API to find species taxonomy data

from math import log
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from ..services.gbif import GbifTaxonSearch

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/taxon")
async def search_taxon(q: str):
    """
    Search for species taxonomy data using the GBIF API.

    Args:
        species (str): The species name to search for.

    Returns:
        JSONResponse: A JSON response containing the species taxonomy data or an error message.
    """
    if not q:
        raise HTTPException(
            status_code=400, detail="Species name is required"
        )
    logger.info(f"Searching for taxon: {q}")
    gbif_service = GbifTaxonSearch()
    try:
        taxon_data = await gbif_service.search(q)
        if not taxon_data:
            return JSONResponse(
                content={
                    "message": "No data found for the given species"
                },
                status_code=404,
            )
        return JSONResponse(content=taxon_data, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
