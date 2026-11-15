import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..configs.config import ColConfig
from ..database.model import ColRelease
from ..services.col import read_release
from ..services.col_match_codes import all_descriptions

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/taxonomy/codes", tags=["Species Data"])
def get_taxonomy_codes():
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


@router.get("/taxonomy/release", tags=["Species Data"], response_model=ColRelease)
def get_taxonomy_release(request: Request) -> ColRelease:
    """Return the Catalogue of Life release the backbone was built from.

    Recorded from the release's ``metadata.yaml`` when the backbone was
    ingested, so every attribution on the site can name it without a copy
    maintained by hand in the frontend.

    Raises:
        HTTPException: 404 when no release has been recorded, as when the
            backbone was never ingested or its release carried no metadata.
    """
    release = read_release(request.app.state.duck_db, ColConfig().release_table)

    if release is None:
        raise HTTPException(
            status_code=404, detail="No Catalogue of Life release is recorded."
        )

    return release
