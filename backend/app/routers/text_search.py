from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..services import clip
from ..search.query import SearchResults

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/text-search")
async def search_text(q: str):
    """Search for images based on a text query using CLIP embeddings.

    Args:
        q (str): The text query to search for.

    Returns:
        JSONResponse: A JSON response containing the search results or an error message.

    To query this endpoint, use:
        /text-search/?q=your+search+terms
    """
    query = q.strip() if q else None

    if query is None or query == "":
        return JSONResponse(
            content={
                "error": "Query parameter 'q' is required and cannot be empty."
            },
            status_code=400,
        )

    text_embedder = clip.ClipTextEmbedder()
    text_embedding = text_embedder.get_embedding_from_text(query)
    if text_embedding is None:
        return JSONResponse(
            content={"error": "Failed to compute text embedding"},
            status_code=500,
        )

    try:
        logger.info(
            f"Querying ChromaDB CLIP collection '{text_embedder.get_collection_name}'..."
        )
        search_results = await text_embedder.query(
            query_embedding=text_embedding, n_results=100
        )
        logger.info("ChromaDB CLIP query completed.")
        if search_results is None:
            logger.error(
                "ChromaDB query returned None, indicating a failure."
            )
            return JSONResponse(
                content={
                    "error": "Failed to retrieve search results from ChromaDB"
                },
                status_code=500,
            )
        logger.info(
            f"ChromaDB CLIP query returned {len(search_results.get('ids', []))} results."
        )
        unique_results = SearchResults(search_results).find_best_hit()
        return JSONResponse(content=unique_results, status_code=200)
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
