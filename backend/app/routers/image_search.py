from ..query.images import ImageToImageSearch
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

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
