from ..query.specimen_data import SpecimenData
from ..services.images import ImagePersistData
import logging
import io
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse
from ..query.taxon_data import TaxonSearch

router = APIRouter()
logger = logging.getLogger(__name__)

from fastapi.responses import JSONResponse


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


@router.get(
    "/species/{scientific_name}/ids",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_species_image_ids(
    request: Request, scientific_name: str, limit: int | None = None, offset: int | None = None
):
    """
    Takes in a species name.
    Fetches all the corresponding image IDs.
    Return a list of image IDs.
    Returns a 404 error if images are not found.
    """
    logger.info(f"Fetching image IDs for species: {scientific_name}")

    try:
        # Enforce a safe default and a hard maximum to avoid excessive queries
        MAX_LIMIT = 2000
        DEFAULT_LIMIT = 10
        if limit is None:
            effective_limit = DEFAULT_LIMIT
        else:
            # clamp to [1, MAX_LIMIT]
            try:
                effective_limit = max(1, min(int(limit), MAX_LIMIT))
            except Exception:
                effective_limit = DEFAULT_LIMIT

        # normalize offset
        try:
            effective_offset = max(0, int(offset)) if offset is not None else 0
        except Exception:
            effective_offset = 0

        # Using method that returns image IDs: fetch_image_ids
        # Pass the effective (clamped/defaulted) limit and offset to the service.
        image_ids = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).fetch_image_ids(scientific_name, effective_limit, effective_offset)
        if not image_ids:
            logger.warning(
                f"No images found for species: {scientific_name}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Images not found for species: {scientific_name}",
            )
        return JSONResponse(content=image_ids)
        # returning the IDs in a JSON response
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(
            f"Error fetching image IDs for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching image IDs.",
        )


@router.get(
    "/species/{scientific_name}/thumbnail",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_taxon_thumbnail(
    request: Request, scientific_name: str
):
    """
    Fetches a taxon thumbnail image.
    Returns a 404 error if the thumbnail is not found.
    """
    logger.info(
        f"Fetching taxon thumbnail for species: {scientific_name}"
    )

    try:
        # It's also good practice to wrap calls that might fail
        img_bytes = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).fetch_thumbnail(scientific_name)
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(
            f"Error fetching data for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )

    if img_bytes is None:
        logger.warning(
            f"No thumbnail found for species: {scientific_name}"
        )
        # Correct way to return a 404 error
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail not found for species: {scientific_name}",
        )

    # Correctly stream the image bytes
    return StreamingResponse(
        io.BytesIO(img_bytes), media_type="image/png"
    )


@router.get(
    "/species/{scientific_name}/image",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_species_high_res_image(
    request: Request, scientific_name: str
):
    """
    Fetches a species high-resolution image.
    Returns a 404 error if the image is not found.
    """
    logger.info(
        f"Fetching species high-resolution image for species: {scientific_name}"
    )

    try:
        # It's also good practice to wrap calls that might fail
        img_bytes = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).fetch_image(scientific_name)
        if img_bytes is None:
            logger.warning(
                f"No image found for species: {scientific_name}"
            )
            # Correct way to return a 404 error
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for species: {scientific_name}",
            )

        # Correctly stream the image bytes
        return StreamingResponse(
            io.BytesIO(img_bytes), media_type="image/png"
        )
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(
            f"Error fetching data for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
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
