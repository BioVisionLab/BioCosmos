"""Agent-based semantic search router."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..services.agent import (
    PAGE_SIZE,
    AgentConfigurationError,
    AgentPlannerError,
    AgentPlannerTimeoutError,
    AgentSearchResult,
    AgentSearchService,
    AgentToolFailureError,
)
from ..services.agent_cache import CachedSearch, agent_search_cache, paginate

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_QUERY_CHARACTERS = 500


def _page_content(entry: CachedSearch, offset: int, limit: int) -> dict:
    results, has_more = paginate(entry.rows, offset, limit)
    content: dict = {
        "query": entry.query,
        "searchId": entry.search_id,
        "total": len(entry.rows),
        "offset": offset,
        "limit": limit,
        "hasMore": has_more,
        "results": results,
    }
    if not entry.rows:
        content["message"] = "No species found matching the criteria."
    if entry.warnings:
        content["warnings"] = entry.warnings
    return content


@router.get("/search/agent", tags=["ML Search"])
async def agent_search(
    request: Request,
    q: str | None = None,
    search_id: str | None = None,
    offset: int = 0,
    limit: int = PAGE_SIZE,
    refresh: bool = False,
):
    """Route a natural-language species search through typed search tools.

    The first request runs the planner and caches the full ranked list; it
    returns one page plus a `searchId`. Later pages pass `search_id` and an
    `offset` and are sliced from the cache without re-running the search.
    A repeated query reuses the cached list unless `refresh` is set.
    """
    offset = max(offset, 0)
    limit = min(max(limit, 1), PAGE_SIZE)

    if search_id:
        entry = agent_search_cache.get(search_id)
        if entry is None:
            return JSONResponse(
                content={"error": "Search expired. Please search again."},
                status_code=410,
            )
        return JSONResponse(content=_page_content(entry, offset, limit))

    query = (q or "").strip()
    if not query:
        return JSONResponse(
            content={"error": "Query parameter 'q' is required and cannot be empty."},
            status_code=400,
        )
    if len(query) > MAX_QUERY_CHARACTERS:
        return JSONResponse(
            content={
                "error": (
                    "Query parameter 'q' must not exceed "
                    f"{MAX_QUERY_CHARACTERS} characters."
                )
            },
            status_code=400,
        )

    entry = None if refresh else agent_search_cache.get_by_query(query)
    if entry is not None:
        return JSONResponse(content=_page_content(entry, offset, limit))

    try:
        outcome = await AgentSearchService(request=request).search(query)
        results = [
            AgentSearchResult.model_validate(row).model_dump(by_alias=True)
            for row in outcome.dataframe.to_dicts()
        ]
        warnings = [
            warning.model_dump(exclude_none=True) for warning in outcome.warnings
        ]
        entry = agent_search_cache.put(query, results, warnings)
        return JSONResponse(content=_page_content(entry, offset, limit))
    except AgentConfigurationError:
        logger.error("Agent search is not configured.", exc_info=True)
        return JSONResponse(
            content={
                "error": "Agent search is unavailable. Check the provider credentials "
                "and configured model access."
            },
            status_code=503,
        )
    except AgentPlannerTimeoutError:
        logger.error("Agent planner timed out.", exc_info=True)
        return JSONResponse(
            content={"error": "Agent search timed out. Please try again."},
            status_code=504,
        )
    except (AgentPlannerError, AgentToolFailureError):
        logger.error("Agent search upstream processing failed.", exc_info=True)
        return JSONResponse(
            content={"error": "Agent search could not evaluate the query."},
            status_code=502,
        )
    except Exception:
        logger.error("Unexpected agent search failure.", exc_info=True)
        return JSONResponse(
            content={"error": "An internal error occurred. Please try again later."},
            status_code=500,
        )
