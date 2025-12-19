from ..query.specimen_data import SpecimenData
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from ..query.taxon_data import TaxonSearch
from ..query.species_similarity import (
    SpeciesSimilarity,
    VisuallySimilarSpeciesPayload,
)
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/species/{scientific_name}/biology", tags=["Species Data"]
)
async def fetch_species_biology(
    request: Request, scientific_name: str
):
    """
    Get species taxonomy data, traits, and similar species.

    Args:
        scientific_name (str): The species name to search for.

    Returns:
        JSONResponse: A JSON response containing the species taxonomy data,
        traits, and similar species based on image similarity analyses
        or an error message.
    """
    logger.info("Received taxon search request")
    scientific_name = (
        scientific_name.strip().lower() if scientific_name else None
    )
    if scientific_name is None or scientific_name == "":
        logger.warning("Taxon search query is empty")
        return JSONResponse(
            content={
                "error": "Query parameter 'scientific_name' is required and cannot be empty."
            },
            status_code=400,
        )
    logger.info(f"Searching for taxon: {scientific_name}")
    try:
        taxon_data = await TaxonSearch(
            request=request, query=scientific_name
        ).search()
        if taxon_data is None:
            message = f"No data found for species: {scientific_name}"
            logger.info(message)
            return JSONResponse(
                content={"message": message},
                status_code=404,
            )
        logger.info(f"Taxon data found for: {scientific_name}")
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


def get_species_similarity(request: Request) -> SpeciesSimilarity:
    return SpeciesSimilarity(request=request, limit=10)


@router.get(
    "/species/{scientific_name}/similar",
    tags=["Species Data", "ML Search"],
    response_model=VisuallySimilarSpeciesPayload,
)
async def fetch_visually_similar_species(
    scientific_name: str,
    service: SpeciesSimilarity = Depends(get_species_similarity),
) -> dict:
    """
    Fetch visually similar species based on image similarity analyses.
    Returns 404 if no similar species are found.
    """
    logger.info(
        "Fetching visually similar species for: %s", scientific_name
    )

    try:
        similar_species = service.find_similar_species(
            scientific_name
        )
        if similar_species is None:
            logger.warning(
                f"No visually similar species found for: {scientific_name}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Visually similar species not found for: {scientific_name}",
            )

        return similar_species
    except HTTPException:
        raise
    except Exception:
        # Includes stack trace.
        logger.exception(
            f"Unhandled error fetching visually similar species for: {scientific_name}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching visually similar species.",
        )


@router.get(
    "/species/{scientific_name}/specimens", tags=["Species Data"]
)
async def fetch_species_specimen_info(
    request: Request, scientific_name: str
):
    """
    Fetches species specimens.
    Returns a 404 error if no specimens are found.
    """
    logger.info(
        f"Fetching species specimens for species: {scientific_name}"
    )

    try:
        specimens = SpecimenData(request=request).summarize(
            species=scientific_name
        )
        if not specimens:
            logger.warning(
                f"No specimens found for species: {scientific_name}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Specimens not found for species: {scientific_name}",
            )
        return JSONResponse(content=specimens)
    except Exception as e:
        logger.error(
            f"Error fetching specimens for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching specimens.",
        )
