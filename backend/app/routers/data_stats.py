import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..database.model import UmapEmbedding
from ..query.country_diversity import CountryDiversity
from ..query.embedding_stats import (
    EmbeddingDistribution,
    EmbeddingStatsPayload,
)
from ..query.specimen_data import SpeciesUmap
from ..query.taxon_data import TaxonSearch
from .http_cache import NO_STORE, SIMILARITY_CACHE_CONTROL, cached_json

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


def get_country_diversity(request: Request) -> CountryDiversity:
    """One instance per process, so the aggregation runs once, not per request."""
    service = getattr(request.app.state, "country_diversity", None)
    if service is None:
        service = CountryDiversity(request.app.state.duck_db)
        request.app.state.country_diversity = service
    return service


# One day, the same policy as the similarity panel: the numbers only change
# when the coordinate validation or taxonomy is rebuilt, with no fingerprint to
# hang an ETag on.
COUNTRY_CACHE_CONTROL = SIMILARITY_CACHE_CONTROL


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        content={"message": message},
        status_code=404,
        headers={"Cache-Control": NO_STORE},
    )


@router.get("/stats/country", tags=["Data Statistics"])
async def get_country_diversity_stats(
    service: CountryDiversity = Depends(get_country_diversity),
):
    """
    Species richness per validated country.

    Countries come from the geoharmonize coordinate validation, normalized to
    ISO 3166-1 alpha-2 with the shared harmonize-core lookup.
    """
    try:
        data = service.summary()
    except Exception as e:
        logger.error(f"Error computing country diversity: {e}", exc_info=True)
        return JSONResponse(
            content={"message": "An error occurred while computing country diversity."},
            status_code=500,
            headers={"Cache-Control": NO_STORE},
        )
    if data is None:
        return _not_found("No coordinate validation is available.")
    return cached_json(data, cache_control=COUNTRY_CACHE_CONTROL)


@router.get("/stats/country/{country_code}", tags=["Data Statistics"])
async def get_country_species(
    country_code: str,
    service: CountryDiversity = Depends(get_country_diversity),
):
    """
    The species recorded in one country (ISO 3166-1 alpha-2, any case).
    """
    code = country_code.strip()
    if len(code) != 2 or not code.isalpha():
        return _not_found(f"Not an ISO 3166-1 alpha-2 code: {country_code}")
    try:
        data = service.species(code)
    except Exception as e:
        logger.error(f"Error fetching species for country {code}: {e}", exc_info=True)
        return JSONResponse(
            content={"message": "An error occurred while fetching country species."},
            status_code=500,
            headers={"Cache-Control": NO_STORE},
        )
    if data is None:
        return _not_found(f"No validated records for country: {code.upper()}")
    return cached_json(data, cache_control=COUNTRY_CACHE_CONTROL)
