import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..database.ingestion_state import IngestionState
from ..query.higher_taxa import FamilyOverview, GenusOverview
from ..query.specimen_data import SpecimenData
from ..query.taxon_data import TaxonSearch, FamilySearch, GenusSearch, SpeciesSearch
from ..query.species_similarity import (
    SpeciesSimilarity,
    VisuallySimilarSpeciesPayload,
)
from ..query.precomputed_similarity import PrecomputedSpeciesSimilarity
from ..services.col import ColTaxonSearch
from ..services.crossref import CrossrefClient, get_crossref_client
from ..services.literature import LiteratureSearch
from .http_cache import (
    LITERATURE_CACHE_CONTROL,
    LITERATURE_PARTIAL_CACHE_CONTROL,
    NO_STORE,
    SIMILARITY_CACHE_CONTROL,
    cached_json,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/species/{scientific_name}/biology", tags=["Species Data"]
)
async def fetch_species_biology(
    request: Request, scientific_name: str
):
    """
    Get species taxonomy data, traits, and similar species.

    Args:
        scientific_name (str): The species name to search for.

    Returns:
        JSONResponse: A JSON response containing the species taxonomy data,
        traits, and similar species based on image similarity analyses
        or an error message.
    """
    logger.info("Received taxon search request")
    scientific_name = (
        scientific_name.strip().lower() if scientific_name else None
    )
    if scientific_name is None or scientific_name == "":
        logger.warning("Taxon search query is empty")
        return JSONResponse(
            content={
                "error": "Query parameter 'scientific_name' is required and cannot be empty."
            },
            status_code=400,
        )
    logger.info(f"Searching for taxon: {scientific_name}")
    try:
        taxon_data = await TaxonSearch(
            request=request, query=scientific_name
        ).search()
        if taxon_data is None:
            message = f"No data found for species: {scientific_name}"
            logger.info(message)
            return JSONResponse(
                content={"message": message},
                status_code=404,
            )
        logger.info(f"Taxon data found for: {scientific_name}")
        logger.info(f"Taxon data: {taxon_data}")
        return JSONResponse(content=taxon_data, status_code=200)
    except Exception as e:
        logger.error(f"Error searching for taxon: {e}", exc_info=True)
        return JSONResponse(
            content={
                "message": f"An error occurred while searching for taxon: {str(e)}"
            },
            status_code=500,
        )


def get_literature_search(
    request: Request, crossref: CrossrefClient = Depends(get_crossref_client)
) -> LiteratureSearch:
    return LiteratureSearch(ColTaxonSearch(request.app.state.duck_db), crossref)


@router.get("/species/{scientific_name}/literature", tags=["Species Data"])
async def fetch_species_literature(
    scientific_name: str,
    search: LiteratureSearch = Depends(get_literature_search),
):
    """
    Publications on a species from CrossRef.

    Searches the accepted name and its Catalogue of Life synonyms. When fewer
    than ten papers name the species, `genusRelated` adds papers on other
    species of its genus; it is null when that search was not needed.
    `partial` is true when a CrossRef request failed, and the response is then
    cached only briefly.
    """
    try:
        payload = await search.search(scientific_name)
    except Exception:
        logger.exception(f"Error searching literature for {scientific_name}")
        return JSONResponse(
            content={"message": "An error occurred while searching literature."},
            status_code=500,
            headers={"Cache-Control": NO_STORE},
        )
    if payload is None:
        return JSONResponse(
            content={"message": f"Not a species name: {scientific_name}"},
            status_code=404,
            headers={"Cache-Control": NO_STORE},
        )
    return cached_json(
        payload.model_dump(mode="json", by_alias=True),
        cache_control=(
            LITERATURE_PARTIAL_CACHE_CONTROL
            if payload.partial
            else LITERATURE_CACHE_CONTROL
        ),
    )


def get_species_similarity(request: Request) -> SpeciesSimilarity:
    return SpeciesSimilarity(request=request, limit=10)


def get_precomputed_similarity(request: Request) -> PrecomputedSpeciesSimilarity:
    return PrecomputedSpeciesSimilarity(request=request, limit=10)


def _similar_species_response(result: dict) -> JSONResponse:
    """Serialize through the payload model, then attach a cache policy.

    Returning a `JSONResponse` bypasses `response_model`, and that model
    camel-cases its fields on the way out (`alias_generator=to_camel`). The
    aliasing has to be applied here or the frontend would silently start
    receiving snake_case keys.

    No ETag: unlike the higher-taxon overviews there is no ingestion
    fingerprint for the similarity table to tie one to, so the entry ages out
    instead.
    """
    payload = VisuallySimilarSpeciesPayload.model_validate(result).model_dump(
        mode="json", by_alias=True
    )
    return cached_json(payload, cache_control=SIMILARITY_CACHE_CONTROL)


@router.get(
    "/species/{scientific_name}/similar",
    tags=["Species Data", "ML Search"],
    response_model=VisuallySimilarSpeciesPayload,
)
async def fetch_visually_similar_species(
    scientific_name: str,
    side: Literal["dorsal", "ventral"] | None = None,
    precomputed: PrecomputedSpeciesSimilarity = Depends(get_precomputed_similarity),
    runtime: SpeciesSimilarity = Depends(get_species_similarity),
):
    """
    Fetch visually similar species based on image similarity analyses.
    Uses precomputed results when available, falls back to runtime vector search.
    Returns 404 if no similar species are found.

    `side` narrows the search to one view, leaving the other list empty. The
    panel asks for dorsal and ventral separately so each can paint as soon as
    it lands rather than both waiting on the slower one; omitted, the response
    is exactly what it has always been.

    Both lookups are synchronous DuckDB and LanceDB work, so they are handed to
    a worker thread. Called inline from this `async def` they held uvicorn's
    event loop for the length of the search, and every thumbnail, image
    metadata and taxonomy request the species page was waiting on queued behind
    them — which is what made the overview tab paint in pieces and look like it
    needed a refresh.
    """
    logger.info(
        "Fetching visually similar species for: %s", scientific_name
    )

    try:
        # Try precomputed first
        result = await asyncio.to_thread(
            precomputed.find_similar_species, scientific_name, side
        )
        if result is not None:
            logger.info(
                "Returning precomputed similarity for: %s",
                scientific_name,
            )
            return _similar_species_response(result)

        # Fallback to runtime vector search
        logger.info(
            "Falling back to runtime similarity for: %s",
            scientific_name,
        )
        similar_species = await asyncio.to_thread(
            runtime.find_similar_species, scientific_name, side
        )
        if similar_species is None:
            logger.warning(
                f"No visually similar species found for: {scientific_name}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Visually similar species not found for: {scientific_name}",
            )

        return _similar_species_response(similar_species)
    except HTTPException as error:
        error.headers = {**(error.headers or {}), "Cache-Control": NO_STORE}
        raise
    except Exception:
        logger.exception(
            f"Unhandled error fetching visually similar species for: {scientific_name}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching visually similar species.",
            headers={"Cache-Control": NO_STORE},
        )


@router.get(
    "/species/{scientific_name}/specimens", tags=["Species Data"]
)
async def fetch_species_specimen_info(
    request: Request, scientific_name: str
):
    """
    Fetches species specimens.
    Returns a 404 error if no specimens are found.
    """
    logger.info(
        f"Fetching species specimens for species: {scientific_name}"
    )

    try:
        specimens = SpecimenData(request=request).summarize(
            species=scientific_name
        )
        if not specimens:
            logger.warning(
                f"No specimens found for species: {scientific_name}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"Specimens not found for species: {scientific_name}",
            )
        return JSONResponse(content=specimens)
    except Exception as e:
        logger.error(
            f"Error fetching specimens for {scientific_name}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while fetching specimens.",
        )


def _overview_etag(request: Request, rank: str, key: str) -> str | None:
    """Tie the ETag to the ingestion that produced the payload.

    A re-ingestion changes the backbone fingerprint, which changes every
    higher-taxon ETag at once — the only way to retire a thirty-day cache
    entry early once a shared cache sits in front of this service.
    """
    try:
        fingerprint = IngestionState(request.app.state.duck_db).get("col_taxonomy")
    except Exception:  # noqa: BLE001 - an ETag is never worth failing a request
        return None
    return f"{rank}:{key}:{fingerprint}" if fingerprint else None


@router.get("/family/{family_name}", tags=["Species Data"])
async def fetch_family_overview(request: Request, family_name: str):
    """Everything the family page renders: classification, counts, tree, images.

    One endpoint rather than three, because the tree, the counts and the image
    strip all come off the same scan of the collection. Splitting them would
    triple the work and give a proxy three chances to hold inconsistent
    generations of one page.
    """
    try:
        overview = await FamilyOverview(request=request, name=family_name).overview()
        if not overview:
            raise HTTPException(
                status_code=404, detail=f"No data found for family: {family_name}"
            )
        return cached_json(
            overview, etag=_overview_etag(request, "family", family_name.lower())
        )
    except HTTPException as error:
        error.headers = {**(error.headers or {}), "Cache-Control": NO_STORE}
        raise
    except Exception:
        logger.exception(f"Error fetching family overview for {family_name}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred.",
            headers={"Cache-Control": NO_STORE},
        )


@router.get("/genus/{genus_name}", tags=["Species Data"])
async def fetch_genus_overview(request: Request, genus_name: str):
    """Everything the genus page renders. Same shape as the family overview."""
    try:
        overview = await GenusOverview(request=request, name=genus_name).overview()
        if not overview:
            raise HTTPException(
                status_code=404, detail=f"No data found for genus: {genus_name}"
            )
        return cached_json(
            overview, etag=_overview_etag(request, "genus", genus_name.lower())
        )
    except HTTPException as error:
        error.headers = {**(error.headers or {}), "Cache-Control": NO_STORE}
        raise
    except Exception:
        logger.exception(f"Error fetching genus overview for {genus_name}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred.",
            headers={"Cache-Control": NO_STORE},
        )


@router.get("/family/{family_name}/classification", tags=["Species Data"])
async def fetch_family_classification(request: Request, family_name: str):
    """
    Get GBIF classification data for a family.
    """
    try:
        results = await FamilySearch(request=request, query=family_name).get_classification()
        if not results:
            raise HTTPException(status_code=404, detail=f"No classification found for family: {family_name}")
        return JSONResponse(content=results, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching family classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.get("/genus/{genus_name}/classification", tags=["Species Data"])
async def fetch_genus_classification(request: Request, genus_name: str):
    """
    Get GBIF classification data for a genus.
    """
    try:
        results = await GenusSearch(request=request, query=genus_name).get_classification()
        if not results:
            raise HTTPException(status_code=404, detail=f"No classification found for genus: {genus_name}")
        return JSONResponse(content=results, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching genus classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.get("/species/{genus}/{specific_epithet}/classification", tags=["Species Data"])
async def fetch_species_classification_by_parts(
    request: Request, genus: str, specific_epithet: str
):
    """
    Get GBIF classification data for a species using genus and specificEpithet.
    """
    try:
        results = await SpeciesSearch(
            request=request, genus=genus, specific_epithet=specific_epithet
        ).get_classification()
        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No classification found for species: {genus} {specific_epithet}",
            )
        return JSONResponse(content=results, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching species classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")
