from ..services.images import ImagePersistData
import logging
import io
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/taxon/{species_name}/thumbnail")
async def fetch_taxon_thumbnail(species_name: str):
    """
    Fetches a taxon thumbnail image.
    Returns a 404 error if the thumbnail is not found.
    """
    logger.info(
        f"Fetching taxon thumbnail for species: {species_name}"
    )

    try:
        # It's also good practice to wrap calls that might fail
        img_bytes = ImagePersistData().fetch_thumbnail(species_name)
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(f"Error fetching data for {species_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )

    if img_bytes is None:
        logger.warning(
            f"No thumbnail found for species: {species_name}"
        )
        # Correct way to return a 404 error
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail not found for species: {species_name}",
        )

    # Correctly stream the image bytes
    return StreamingResponse(
        io.BytesIO(img_bytes), media_type="image/png"
    )


@router.get("/taxon/{species_name}/image")
async def fetch_taxon_img(species_name: str):
    """
    Fetches a taxon image.
    Return a high-res taxon image.
    Returns a 404 error if the image is not found.
    """
    logger.info(f"Fetching taxon image for species: {species_name}")

    try:
        # It's also good practice to wrap calls that might fail
        img_bytes = ImagePersistData().fetch_image(species_name)
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(f"Error fetching data for {species_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )

    if img_bytes is None:
        logger.warning(f"No image found for species: {species_name}")
        # Correct way to return a 404 error
        raise HTTPException(
            status_code=404,
            detail=f"Image not found for species: {species_name}",
        )

    # Correctly stream the image bytes
    return StreamingResponse(
        io.BytesIO(img_bytes), media_type="image/png"
    )
