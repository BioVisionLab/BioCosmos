from enum import unique
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from ..services import unicom
from ..searches.query import SearchResults

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/img-search")
async def image_search(request: Request):
    """ """

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

        # 1. Get image embedding from base64 using UNICOM
        logger.info(
            "Generating UNICOM image embedding from base64 data..."
        )
        embedder = unicom.UnicomImageEmbedder()
        if embedder.model is None:
            logger.error(
                "UNICOM model is not available for image embedding."
            )
            return JSONResponse(
                content={
                    "error": "UNICOM model is not available for image embedding."
                },
                status_code=500,
            )
        query_embeddings = embedder.get_embedding(base64_image)
        if query_embeddings is None:
            # Error logged in helper function
            return JSONResponse(
                content={
                    "error": "Failed to process uploaded image using UNICOM."
                },
                status_code=400,
            )
        logger.info("UNICOM image embedding generated.")

        # 2. Search UNICOM ChromaDB collection
        logger.info(
            f"Querying ChromaDB UNICOM collection '{embedder.get_collection_name}' with image embedding..."
        )
        search_results = await embedder.query(
            query_embedding=query_embeddings, n_results=100
        )
        logger.info("ChromaDB UNICOM query completed.")

        unique_results = SearchResults(search_results).find_best_hit()
        return JSONResponse(content=unique_results, status_code=200)

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
