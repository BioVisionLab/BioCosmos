import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..database.model import UmapEmbedding
from ..query.embedding_stats import (
    EmbeddingDistribution,
    EmbeddingStatsPayload,
)
from ..query.specimen_data import SpeciesUmap
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


def get_species_umap(request: Request) -> UmapEmbedding:
    return SpeciesUmap(request=request)


@router.get(
    "/stats/umap/{species}",
    tags=["Data Statistics"],
    response_model=UmapEmbedding,
)
async def get_umap_stats(
    species: str,
    service: UmapEmbedding = Depends(get_species_umap),
):
    """
    Get UMAP statistics for a given species.
    """
    logger.info(f"Received UMAP stats request for species: {species}")
    try:
        data = service.get_umap_embeddings(species)
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


def get_embedding_distribution(request: Request) -> EmbeddingDistribution:
    return EmbeddingDistribution(request=request)


@router.get(
    "/stats/embeddings",
    tags=["Data Statistics"],
    response_model=EmbeddingStatsPayload,
)
async def get_embedding_stats(
    service: EmbeddingDistribution = Depends(get_embedding_distribution),
):
    """
    Get the distribution of CLIP and UNICOM embedding values.
    """
    logger.info("Received embedding distribution request")
    try:
        data = service.get_distributions()
        if data is None:
            logger.info("No embedding distributions found")
            return JSONResponse(
                content={"message": "No embedding statistics found"},
                status_code=404,
            )
        logger.info("Embedding distributions computed successfully")
        return JSONResponse(content=data, status_code=200)
    except Exception as e:
        logger.error(
            f"Error fetching embedding distributions: {e}", exc_info=True
        )
        return JSONResponse(
            content={
                "message": f"An error occurred while fetching embedding statistics: {str(e)}"
            },
            status_code=500,
        )
