from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/img-search")
async def image_search(q: str):
    """

    """
    query: str = q.strip()

    if query is None or query == "":
        logger.exception("Query parameter 'q' is required and cannot be empty.")
        return JSONResponse(content={"error": "Query parameter 'q' is required and cannot be empty."}, status_code=400)
    
    return JSONResponse(content={"query": query, "results": []}, status_code=200)
