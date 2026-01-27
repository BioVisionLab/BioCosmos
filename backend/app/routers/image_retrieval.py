from http.client import HTTPException
from fastapi import APIRouter, Request
from ..query.image_files import ImageFileRetrieval, ImageMetaRetrieval
from fastapi.responses import FileResponse, JSONResponse
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/image/id/{image_id}", tags=["Taxon Images"])
async def image_search_by_id(
    request: Request, image_id: str
) -> FileResponse:
    """
    Get an image by its ID.
    Expects an image ID as a path parameter.
    Returns the image url.
    """

    logger.info(
        f"Received image search request for image ID: {image_id}"
    )
    try:
        img_path = ImageFileRetrieval(request=request).get_full_res(
            image_id
        )
        if img_path is None:
            logger.warning(f"Image not found for ID: {image_id}")
            raise HTTPException(
                status_code=404,
                detail="Image not found for the given ID.",
            )
        # Correctly stream the image bytes
        return FileResponse(img_path)
    except HTTPException:
        raise  # preserve 404, 400, etc
    except Exception as e:
        logger.error(
            f"Error during image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during image fetch by ID.",
        )


@router.get("/image/id/{image_id}/thumbnail", tags=["Taxon Images"])
async def image_search_thumbnail_by_id(
    request: Request, image_id: str
):
    """
    Endpoint for fetching thumbnail image by image ID.
    Expects an image ID as a path parameter.
    Returns the thumbnail image.
    """

    logger.info(
        f"Received thumbnail image request for image ID: {image_id}"
    )
    try:
        img_path = ImageFileRetrieval(request=request).get_thumbnail(
            image_id
        )
        if img_path is None:
            logger.warning(
                f"Thumbnail image not found for ID: {image_id}"
            )
            raise HTTPException(
                status_code=404,
                detail="Thumbnail image not found for the given ID.",
            )
        # Correctly stream the image bytes
        return FileResponse(img_path)
    except HTTPException:
        raise  # preserve 404, 400, etc
    except Exception as e:
        logger.error(
            f"Error during image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during image fetch by ID.",
        )


@router.get(
    "/image/{scientific_name}/metadata",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_species_image_ids(
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
        image_ids = ImageMetaRetrieval(
            request=request
        ).get_species_image_ids(scientific_name)
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
    "/image/{scientific_name}/thumbnail",
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
        img_path = ImageFileRetrieval(
            request=request
        ).get_species_thumbnail(scientific_name)
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(
            f"Error fetching data for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )

    if img_path is None:
        logger.warning(
            f"No thumbnail found for species: {scientific_name}"
        )
        # Correct way to return a 404 error
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail not found for species: {scientific_name}",
        )

    # Correctly stream the image bytes
    return FileResponse(img_path)


@router.get(
    "/image/{scientific_name}/high-resolution",
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
        img_path = ImageFileRetrieval(
            request=request
        ).get_species_image(scientific_name)
        if img_path is None:
            logger.warning(
                f"No image found for species: {scientific_name}"
            )
            # Correct way to return a 404 error
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for species: {scientific_name}",
            )

        # Correctly stream the image bytes
        return FileResponse(img_path)
    except Exception as e:
        # Catch potential errors from the data fetching logic itself
        logger.error(
            f"Error fetching data for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )
