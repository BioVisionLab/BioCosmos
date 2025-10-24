from ..query.image_search import TextToImageSearch
from ..query.image_search import ImageToImageSearch

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search/text", tags=["ML Search"])
async def search_text(request: Request, q: str, limit: int = 50):
    """Endpoint for text to image search.

    Expects a query parameter 'q' for the search term.
    Returns a list of search results based on the text embedding.
    Args:
        q (str): The search query string.
    Returns:
        JSONResponse: A response containing the search results or an error message.
    """
    query = q.strip() if q else None

    if query is None or query == "":
        return JSONResponse(
            content={
                "error": "Query parameter 'q' is required and cannot be empty."
            },
            status_code=400,
        )
    try:
        search = TextToImageSearch(
            request=request, query=query, limit=limit
        )
        search_results = search.search()
        if not search_results:
            logger.error(
                f"No search results returned from '{query}'."
            )
            return JSONResponse(
                content={
                    "error": f"No search results found for '{query}'."
                },
                status_code=500,
            )
        return JSONResponse(content=search_results, status_code=200)
    except Exception as e:
        logger.error(
            f"Error during CLIP text search for query '{query}': {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={
                "error": "An internal error occurred during text search."
            },
            status_code=500,
        )


@router.get("/search/image", tags=["ML Search"])
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
