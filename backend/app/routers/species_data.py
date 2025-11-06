from ..query.specimen_data import SpecimenData
from ..services.images import ImagePersistData
import logging
import io
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# New: adding a backend endpoint to fetch image IDs for a species
from fastapi.responses import JSONResponse


@router.get(
    "/species/{scientific_name}/ids",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_species_images(
    request: Request, scientific_name: str
):
    """
    Takes in a species name.
    Fetches all the corresponding image IDs.
    Return a list of image IDs.
    Returns a 404 error if images are not found.
    """
    logger.info(f"Fetching image IDs for species: {scientific_name}")

    try:
        # Using method that returns image IDs: fetch_image_ids
        image_ids = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).fetch_image_ids(scientific_name)
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
async def fetch_taxon_img(request: Request, scientific_name: str):
    """
    Fetches a taxon image.
    Return a high-res taxon image.
    Returns a 404 error if the image is not found.
    """
    logger.info(
        f"Fetching taxon image for species: {scientific_name}"
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
async def fetch_taxon_specimens(
    request: Request, scientific_name: str
):
    """
    Fetches taxon specimens.
    Returns a 404 error if no specimens are found.
    """
    logger.info(
        f"Fetching taxon specimens for species: {scientific_name}"
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
