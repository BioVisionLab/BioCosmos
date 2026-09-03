import logging

from fastapi import APIRouter, Request
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ..query.image_files import ImageFileRetrieval, ImageMetaRetrieval

router = APIRouter()

# Bounds for the paged species image-ID endpoint.
DEFAULT_IMAGE_ID_LIMIT = 100
MAX_IMAGE_ID_LIMIT = 500

logger = logging.getLogger(__name__)


@router.get("/image/id/{image_id}", tags=["Taxon Images"])
async def image_search_by_id(request: Request, image_id: str) -> FileResponse:
    """
    Get an image by its ID.
    Expects an image ID as a path parameter.
    Returns the image url.
    """

    logger.info(f"Received image search request for image ID: {image_id}")
    try:
        img_path = ImageFileRetrieval(request=request).get_full_res(image_id)
        if img_path is None:
            logger.warning(f"Image not found for ID: {image_id}")
            raise HTTPException(
                status_code=404,
                detail="Image not found for the given ID.",
            )
        return FileResponse(img_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error during image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during image fetch by ID.",
        )


@router.get("/image/id/{image_id}/metadata", tags=["Taxon Images"])
async def image_metadata_by_id(request: Request, image_id: str):
    """
    Fetch metadata for a single image ID.
    Returns a JSON object of metadata fields or 404 if not found.
    """
    logger.info(f"Fetching metadata for image ID: {image_id}")
    try:
        meta = ImageMetaRetrieval(request=request).get_meta_by_id(image_id)
        if not meta:
            logger.warning(f"No metadata found for image ID: {image_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Metadata not found for image ID: {image_id}",
            )
        return JSONResponse(content=meta, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching metadata for {image_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching image metadata.",
        )


@router.get("/image/id/{image_id}/thumbnail", tags=["Taxon Images"])
async def image_search_thumbnail_by_id(request: Request, image_id: str):
    """
    Endpoint for fetching thumbnail image by image ID.
    Expects an image ID as a path parameter.
    Returns the thumbnail image.
    """

    logger.info(f"Received thumbnail image request for image ID: {image_id}")
    try:
        img_path = ImageFileRetrieval(request=request).get_thumbnail(image_id)
        if img_path is None:
            logger.warning(f"Thumbnail image not found for ID: {image_id}")
            raise HTTPException(
                status_code=404,
                detail="Thumbnail image not found for the given ID.",
            )
        return FileResponse(img_path)
    except HTTPException:
        raise
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
    request: Request,
    scientific_name: str,
    limit: int = DEFAULT_IMAGE_ID_LIMIT,
    offset: int = 0,
):
    """
    Takes in a species name.
    Fetches a page of the corresponding image IDs.

    Args:
        scientific_name (str): The species to fetch image IDs for.
        limit (int, optional): Maximum IDs to return. Clamped to
            1..MAX_IMAGE_ID_LIMIT. Defaults to DEFAULT_IMAGE_ID_LIMIT.
        offset (int, optional): Number of IDs to skip. Defaults to 0.

    Returns a list of image IDs. Returns a 404 only when the first page is
    empty; paging past the end yields an empty list so that callers can detect
    exhaustion without treating it as an error.
    """
    limit = max(1, min(limit, MAX_IMAGE_ID_LIMIT))
    offset = max(0, offset)
    logger.info(
        f"Fetching image IDs for species: {scientific_name} "
        f"(limit={limit}, offset={offset})"
    )

    try:
        image_ids = ImageMetaRetrieval(request=request).get_species_image_ids(
            scientific_name, limit=limit, offset=offset
        )
    except Exception as e:
        logger.error(f"Error fetching image IDs for {scientific_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching image IDs.",
        )

    if not image_ids and offset == 0:
        logger.warning(f"No images found for species: {scientific_name}")
        raise HTTPException(
            status_code=404,
            detail=f"Images not found for species: {scientific_name}",
        )
    return JSONResponse(content=image_ids)


@router.get(
    "/image/{scientific_name}/thumbnail",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_taxon_thumbnail(request: Request, scientific_name: str):
    """
    Fetches a taxon thumbnail image.
    Returns a 404 error if the thumbnail is not found.
    """
    logger.info(f"Fetching taxon thumbnail for species: {scientific_name}")

    try:
        img_path = ImageFileRetrieval(request=request).get_species_thumbnail(
            scientific_name
        )
    except Exception as e:
        logger.error(f"Error fetching data for {scientific_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )

    if img_path is None:
        logger.warning(f"No thumbnail found for species: {scientific_name}")
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail not found for species: {scientific_name}",
        )
    return FileResponse(img_path)


@router.get(
    "/image/{scientific_name}/high-resolution",
    tags=["Species Data", "Taxon Images"],
)
async def fetch_species_high_res_image(request: Request, scientific_name: str):
    """
    Fetches a species high-resolution image.
    Returns a 404 error if the image is not found.
    """
    logger.info(
        f"Fetching species high-resolution image for species: {scientific_name}"
    )

    try:
        img_path = ImageFileRetrieval(request=request).get_species_image(
            scientific_name
        )
        if img_path is None:
            logger.warning(f"No image found for species: {scientific_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for species: {scientific_name}",
            )

        return FileResponse(img_path)
    except Exception as e:
        logger.error(f"Error fetching data for {scientific_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching the image data.",
        )
