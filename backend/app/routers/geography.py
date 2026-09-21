import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services.geo_validation_codes import all_descriptions

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/geography/codes", tags=["Species Data"])
async def get_geography_codes():
    """Return the human-readable description of every coordinate-validation code.

    Serving these once lets per-record payloads carry bare codes while the UI
    still explains them, and keeps a single authored copy of the prose instead
    of a duplicate maintained in the frontend.

    Returns:
        JSONResponse: ``{"validationStatus": {...}, "coordinateCheck": {...},
        "countryCheck": {...}, "adm1Check": {...}}``, each mapping a code to
        its description.
    """
    return JSONResponse(content=all_descriptions(), status_code=200)
