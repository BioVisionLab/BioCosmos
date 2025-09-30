from ..searches.images import ImageToImageSearch
from ..services.images import ImagePersistData
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from fastapi.responses import Response

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/img-search")
async def image_search(request: Request):
    """
    Endpoint for image to image search.
    Expects a base64 encoded image in the JSON body under the key 'image'.
    Returns a list of search results based on the image embedding.
    """

    logger.info("Received image search request (UNICOM).")
    try:
        data = await request.json()
        if not data or "image" not in data:
            logger.warning(
                "Image search request missing 'image' field in JSON body."
            )
            return JSONResponse(
                content={
                    "error": "Missing 'image' field in JSON body"
                },
                status_code=400,
            )

        base64_image = data["image"]
        if not base64_image or not str(base64_image).strip():
            logger.warning(
                "Image search request contains empty 'image' field."
            )
            return JSONResponse(
                content={
                    "error": "Missing 'image' field in JSON body"
                },
                status_code=400,
            )

        logger.info(
            "Generating UNICOM image embedding from base64 data..."
        )
        img_service = ImageToImageSearch(request, base64_image)
        search_results = img_service.search()
        if search_results is None:
            logger.warning("No results found for the given image.")
            return JSONResponse(
                content={"results": []},
                status_code=200,
            )

        return JSONResponse(content=search_results, status_code=200)

    except Exception as e:
        logger.error(
            f"Error during UNICOM image search: {e}", exc_info=True
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during image search."
            },
            status_code=500,
        )


@router.get("/img-search/id/{image_id}")
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


@router.get("/img-search/id/{image_id}/thumbnail")
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
