from http.client import HTTPException
from ..query.image_files import ImageFileRetrieval
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/image/id/{image_id}")
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
    except Exception as e:
        logger.error(
            f"Error during image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during image fetch by ID.",
        )


@router.get("/image/id/{image_id}/thumbnail")
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
    except Exception as e:
        logger.error(
            f"Error during thumbnail image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during thumbnail image fetch by ID.",
        )
