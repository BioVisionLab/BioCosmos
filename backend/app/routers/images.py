from ..services.images import ImagePersistData
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from fastapi.responses import Response

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/image/id/{image_id}")
async def image_search_by_id(request: Request, image_id: str):
    """
    Endpoint for image to image search by image ID.
    Expects an image ID as a path parameter.
    Returns a list of search results based on the image embedding.
    """

    logger.info(
        f"Received image search request for image ID: {image_id}"
    )
    try:
        img_bytes = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).get_img_by_id(image_id)
        if img_bytes is None:
            logger.warning(f"Image not found for ID: {image_id}")
            return JSONResponse(
                content={
                    "error": "Image not found for the given ID."
                },
                status_code=404,
            )
        # Correctly stream the image bytes
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        logger.error(
            f"Error during image search by ID {image_id}: {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during image search by ID."
            },
            status_code=500,
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
        img_bytes = ImagePersistData(
            lance_db=request.app.state.lance_db
        ).get_img_by_id(image_id, is_thumbnail=True)
        if img_bytes is None:
            logger.warning(
                f"Thumbnail image not found for ID: {image_id}"
            )
            return JSONResponse(
                content={
                    "error": "Thumbnail image not found for the given ID."
                },
                status_code=404,
            )
        # Correctly stream the image bytes
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        logger.error(
            f"Error during thumbnail image fetch by ID {image_id}: {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during thumbnail image fetch by ID."
            },
            status_code=500,
        )
