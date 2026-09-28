import logging
from typing import Literal

import duckdb
import polars as pl
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..query.morphospace import MorphospaceQuery
from .http_cache import MORPHOSPACE_CACHE_CONTROL, NO_STORE, cached_json

router = APIRouter()

logger = logging.getLogger(__name__)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        content={"message": message},
        status_code=404,
        headers={"Cache-Control": NO_STORE},
    )


def _failed() -> JSONResponse:
    return JSONResponse(
        content={"message": "Morphospace query failed."},
        status_code=500,
        headers={"Cache-Control": NO_STORE},
    )


# Declared before the scope route so `species` is never read as a rank.
@router.get("/morphospace/species/{species}", tags=["Morphospace"])
async def get_species_morphospace(species: str, request: Request):
    """Where one species sits among the species of its genus and family.

    Intraspecific dispersion on each side, dorso-ventral divergence, their
    percentiles within the genus and family, and which of those scopes have a
    morphospace to draw the species in.
    """
    try:
        payload = MorphospaceQuery(request.app.state.duck_db).get_species(species)
    except (duckdb.Error, pl.exceptions.PolarsError):
        logger.exception("Morphospace query failed")
        return _failed()
    if payload is None:
        return _not_found(f"No morphospace for species: {species}")
    return cached_json(payload, cache_control=MORPHOSPACE_CACHE_CONTROL)


@router.get("/morphospace/{rank}/{name}", tags=["Morphospace"])
async def get_scope_morphospace(
    rank: Literal["all", "family", "genus"], name: str, request: Request
):
    """The shared dorso-ventral morphospace of a genus, a family or everything.

    Points are column-wise, one entry per species and side. `extremes` names
    the species at each end of each axis, `disparity` is measured in the full
    embedding, and a family also lists its genera's disparity as `children`.
    Use `all` as the name with the `all` rank.
    """
    try:
        payload = MorphospaceQuery(request.app.state.duck_db).get_scope(rank, name)
    except (duckdb.Error, pl.exceptions.PolarsError):
        logger.exception("Morphospace query failed")
        return _failed()
    if payload is None:
        return _not_found(f"No morphospace for {rank}: {name}")
    return cached_json(
        payload,
        etag=f"{payload['scope']['runId']}-{rank}-{payload['scope']['key']}",
        cache_control=MORPHOSPACE_CACHE_CONTROL,
    )
