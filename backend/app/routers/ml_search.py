import asyncio
import logging

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from ..query.image_search import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_PIXELS,
    ImageToImageSearch,
    TextToImageSearch,
    image_too_large,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search/text", tags=["ML Search"])
def search_text(request: Request, q: str, limit: int = 50):
    """Endpoint for text to image search.

    A plain `def`, so FastAPI runs the embedding and vector search in its
    threadpool instead of on the event loop.

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
            content={"error": "Query parameter 'q' is required and cannot be empty."},
            status_code=400,
        )
    try:
        search = TextToImageSearch(request=request, query=query, limit=limit)
        search_results = search.search()
        if not search_results:
            logger.error(f"No search results returned from '{query}'.")
            return JSONResponse(
                content={"error": f"No search results found for '{query}'."},
                status_code=500,
            )
        return JSONResponse(content=search_results, status_code=200)
    except Exception as e:
        logger.error(
            f"Error during CLIP text search for query '{query}': {e}",
            exc_info=True,
        )
        return JSONResponse(
            content={"error": "An internal error occurred during text search."},
            status_code=500,
        )


@router.post("/search/image", tags=["ML Search"])
async def image_search(request: Request, file: UploadFile = File(...)):
    """
    Endpoint for image to image search.
    Expects an uploaded image file.
    Returns a list of search results based on the image embedding.
    """

    logger.info("Received image search request (UNICOM).")
    try:
        # Validate file upload
        if not file or not file.filename:
            logger.warning("Image search request missing file upload.")
            return JSONResponse(
                content={"error": "Missing image file in request"},
                status_code=400,
            )
        allowed_content_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        ]
        if file.content_type not in allowed_content_types:
            logger.warning(f"Invalid file type: {file.content_type}")
            return JSONResponse(
                content={
                    "error": f"Invalid file type: {file.content_type}. Allowed types are: JPEG, JPG, PNG, WEBP."
                },
                status_code=400,
            )

        # Read one byte past the cap, so an oversized upload is caught
        # without reading all of it into memory.
        image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if not image_bytes:
            logger.warning("Image search request contains empty file.")
            return JSONResponse(
                content={"error": "Uploaded file is empty"},
                status_code=400,
            )

        if len(image_bytes) > MAX_UPLOAD_BYTES or image_too_large(image_bytes):
            logger.warning("Image search upload exceeds the size limit.")
            return JSONResponse(
                content={
                    "error": f"Image is too large. The limit is "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB and "
                    f"{MAX_UPLOAD_PIXELS // 1_000_000} megapixels."
                },
                status_code=413,
            )

        logger.info("Generating UNICOM image embedding from uploaded file...")
        # Pass the image bytes directly to ImageToImageSearch
        # Embedding and the vector search block, so they run in a worker
        # thread rather than stalling every other request on the event loop.
        img_service = ImageToImageSearch(request)
        search_results = await asyncio.to_thread(img_service.search, image_bytes)

        if search_results is None:
            logger.warning("No results found for the given image.")
            return JSONResponse(
                content={"results": []},
                status_code=200,
            )

        return JSONResponse(content=search_results, status_code=200)

    except Exception as e:
        logger.error(f"Error during UNICOM image search: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "An internal error occurred during image search."},
            status_code=500,
        )
