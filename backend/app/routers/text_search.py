from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..services import clip_service

import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/text-search/")
async def search_text(q: str):
    """ Search for images based on a text query using CLIP embeddings.
    Args:
        query (str): The text query to search for.
    Returns:
        JSONResponse: A JSON response containing the search results or an error message.

    To query this endpoint, use:
        /text-search/?query=your+search+terms
    """
    query = q.strip()

    if query is None or query == "":
        return JSONResponse(content={"error": "Query parameter is required"}, status_code=400)
    
    text_embedder = clip_service.ClipTextEmbedder()
    text_embedding = text_embedder.get_embedding(query)
    if text_embedding is None:
        return JSONResponse(content={"error": "Failed to compute text embedding"}, status_code=500)
    
    return JSONResponse(content={"query": query, "text_embedding": text_embedding}, status_code=200)
