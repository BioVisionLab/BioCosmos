"""Agent-based semantic search router."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..services.agent import (
    AgentConfigurationError,
    AgentPlannerError,
    AgentPlannerTimeoutError,
    AgentSearchResult,
    AgentSearchService,
    AgentToolFailureError,
)


router = APIRouter()
logger = logging.getLogger(__name__)

MAX_QUERY_CHARACTERS = 500


@router.get("/search/agent", tags=["ML Search"])
async def agent_search(request: Request, q: str | None = None):
    """Route a natural-language species search through typed search tools."""
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

    try:
        outcome = await AgentSearchService(request=request).search(query)
        results = [
            AgentSearchResult.model_validate(row).model_dump(by_alias=True)
            for row in outcome.dataframe.to_dicts()
        ]
        content: dict = {
            "query": query,
            "total": len(results),
            "results": results,
        }
        if not results:
            content["message"] = "No species found matching the criteria."
        if outcome.warnings:
            content["warnings"] = [
                warning.model_dump(exclude_none=True) for warning in outcome.warnings
            ]
        return JSONResponse(content=content, status_code=200)
    except AgentConfigurationError:
        logger.error("Agent search is not configured.", exc_info=True)
        return JSONResponse(
            content={"error": "Agent search is temporarily unavailable."},
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
