import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services.col_match_codes import all_descriptions

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/taxonomy/codes", tags=["Species Data"])
async def get_taxonomy_codes():
    """Return the human-readable description of every taxonomic-update code.

    Serving these once lets per-record payloads carry bare codes while the UI
    still explains them, and keeps a single authored copy of the prose instead
    of a duplicate maintained in the frontend.

    Returns:
        JSONResponse: ``{"updateStatus": {...}, "matchMethod": {...},
        "reasonCode": {...}}``, each mapping a code to its description. Method
        entries include the rank-cascade forms, e.g. ``GENUS_SPELLING_EPITHET``.
    """
    return JSONResponse(content=all_descriptions(), status_code=200)
