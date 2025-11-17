# Query taxonomy data based on the species name
# Use GBIF Species Search API to find species taxonomy data
from ..query.specimen_data import SpeciesUmap
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


@router.get("/stats/umap/{species}", tags=["Data Statistics"])
async def get_umap_stats(species: str, request: Request):
    """
    Get UMAP statistics for a given species.
    """
    logger.info(f"Received UMAP stats request for species: {species}")
    try:
        data = SpeciesUmap(request=request).get_umap_embeddings(
            species
        )
        if data is None:
            logger.info(f"No UMAP stats found for species: {species}")
            return JSONResponse(
                content={
                    "message": f"No UMAP statistics found for species: {species}"
                },
                status_code=404,
            )
        logger.info(f"UMAP stats found for species {species}: {data}")
        return JSONResponse(content=data, status_code=200)
    except Exception as e:
        logger.error(
            f"Error fetching UMAP stats for species {species}: {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "message": f"An error occurred while fetching UMAP stats for species {species}: {str(e)}"
            },
            status_code=500,
        )
