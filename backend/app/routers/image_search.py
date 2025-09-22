from ..services.images import ImagePersistData
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from ..services import unicom
import io
from fastapi.responses import StreamingResponse

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
            return JSONResponse(
                content={
                    "error": "Failed to process uploaded image using UNICOM."
                },
                status_code=400,
            )
        logger.info("UNICOM image embedding generated.")

        logger.info(
            f"Querying ChromaDB UNICOM collection '{embedder.get_collection_name}' with image embedding..."
        )
        search_results = await embedder.query(
            query_embedding=query_embeddings, n_results=100
        )
        logger.info("ChromaDB UNICOM query completed.")

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
async def image_search_by_id(image_id: str):
    """
    Endpoint for image to image search by image ID.
    Expects an image ID as a path parameter.
    Returns a list of search results based on the image embedding.
    """

    logger.info(
        f"Received image search request for image ID: {image_id}"
    )
    try:
        img_bytes = ImagePersistData().get_img_by_id(image_id)
        if img_bytes is None:
            logger.warning(f"Image not found for ID: {image_id}")
            return JSONResponse(
                content={
                    "error": "Image not found for the given ID."
                },
                status_code=404,
            )
        # Correctly stream the image bytes
        return StreamingResponse(
            io.BytesIO(img_bytes), media_type="image/png"
        )
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
