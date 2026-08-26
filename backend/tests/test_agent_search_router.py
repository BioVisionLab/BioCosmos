"""Router contract tests for agent search."""

import json
from types import SimpleNamespace

import polars as pl
import pytest

from app.routers import agent_search as router_module
from app.services.agent import (
    AgentConfigurationError,
    AgentPlannerError,
    AgentPlannerTimeoutError,
    AgentSearchOutcome,
    AgentToolFailureError,
)
from app.services.agent_tools import AgentWarning


def response_json(response):
    return json.loads(response.body)


@pytest.mark.asyncio
async def test_router_rejects_missing_and_oversized_queries():
    request = SimpleNamespace()

    missing = await router_module.agent_search(request, None)
    oversized = await router_module.agent_search(request, "x" * 501)

    assert missing.status_code == 400
    assert oversized.status_code == 400


@pytest.mark.asyncio
async def test_router_preserves_results_and_adds_partial_warnings(monkeypatch):
    outcome = AgentSearchOutcome(
        dataframe=pl.DataFrame(
            [
                {
                    "imgId": "image-a",
                    "species": "Species a",
                    "score": 0.812345,
                    "tool_names": ["search_by_color"],
                }
            ]
        ),
        warnings=[
            AgentWarning(
                code="tool_execution_failed",
                tool="search_by_location",
                message="This search constraint could not be evaluated.",
            )
        ],
    )

    class FakeService:
        async def search(self, _query):
            return outcome

    monkeypatch.setattr(
        router_module,
        "AgentSearchService",
        lambda request: FakeService(),
    )

    response = await router_module.agent_search(SimpleNamespace(), "blue in Brazil")
    body = response_json(response)

    assert response.status_code == 200
    assert body["query"] == "blue in Brazil"
    assert body["total"] == 1
    assert body["results"] == [
        {
            "imgId": "image-a",
            "species": "Species a",
            "score": 0.8123,
            "tool_names": ["search_by_color"],
        }
    ]
    assert body["warnings"][0]["tool"] == "search_by_location"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (AgentConfigurationError(), 503),
        (AgentPlannerTimeoutError(), 504),
        (AgentPlannerError(), 502),
        (AgentToolFailureError(), 502),
    ],
)
async def test_router_maps_typed_errors(monkeypatch, error, status_code):
    class FakeService:
        async def search(self, _query):
            raise error

    monkeypatch.setattr(
        router_module,
        "AgentSearchService",
        lambda request: FakeService(),
    )

    response = await router_module.agent_search(SimpleNamespace(), "blue")

    assert response.status_code == status_code
    assert "error" in response_json(response)
