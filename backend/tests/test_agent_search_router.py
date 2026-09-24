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
from app.services.agent_cache import agent_search_cache
from app.services.agent_tools import AgentWarning


def response_json(response):
    return json.loads(response.body)


@pytest.fixture(autouse=True)
def clear_search_cache():
    agent_search_cache.clear()
    yield
    agent_search_cache.clear()


def install_fake_service(monkeypatch, rows):
    calls = []

    class FakeService:
        async def search(self, query):
            calls.append(query)
            return AgentSearchOutcome(dataframe=pl.DataFrame(rows), warnings=[])

    monkeypatch.setattr(
        router_module,
        "AgentSearchService",
        lambda request: FakeService(),
    )
    return calls


def ranked_rows(count):
    return [
        {
            "imgId": f"image-{index:03d}",
            "species": f"Species {index:03d}",
            "score": 1.0 - index / 1000,
            "tool_names": ["search_by_color"],
        }
        for index in range(count)
    ]


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
            "speciesKey": None,
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


@pytest.mark.asyncio
async def test_router_pages_results_without_rerunning_search(monkeypatch):
    calls = install_fake_service(monkeypatch, ranked_rows(40))

    first = response_json(await router_module.agent_search(SimpleNamespace(), "blue"))

    assert first["total"] == 40
    assert first["offset"] == 0
    assert first["limit"] == router_module.PAGE_SIZE == 35
    assert first["hasMore"] is True
    assert len(first["results"]) == 35
    assert first["searchId"]

    second = response_json(
        await router_module.agent_search(
            SimpleNamespace(), search_id=first["searchId"], offset=35
        )
    )

    assert calls == ["blue"]
    assert second["query"] == "blue"
    assert second["hasMore"] is False
    assert [row["imgId"] for row in second["results"]] == [
        f"image-{index:03d}" for index in range(35, 40)
    ]


@pytest.mark.asyncio
async def test_router_reuses_cached_query_unless_refreshed(monkeypatch):
    calls = install_fake_service(monkeypatch, ranked_rows(3))

    first = response_json(await router_module.agent_search(SimpleNamespace(), "Blue"))
    repeat = response_json(
        await router_module.agent_search(SimpleNamespace(), "  blue ")
    )

    assert calls == ["Blue"]
    assert repeat["searchId"] == first["searchId"]

    refreshed = response_json(
        await router_module.agent_search(SimpleNamespace(), "blue", refresh=True)
    )

    assert calls == ["Blue", "blue"]
    assert refreshed["searchId"] != first["searchId"]


@pytest.mark.asyncio
async def test_router_rejects_unknown_search_id():
    response = await router_module.agent_search(SimpleNamespace(), search_id="gone")

    assert response.status_code == 410
    assert "error" in response_json(response)


@pytest.mark.asyncio
async def test_router_clamps_offset_and_limit(monkeypatch):
    install_fake_service(monkeypatch, ranked_rows(50))

    body = response_json(
        await router_module.agent_search(
            SimpleNamespace(), "blue", offset=-5, limit=1000
        )
    )

    assert body["offset"] == 0
    assert body["limit"] == 35
    assert len(body["results"]) == 35


@pytest.mark.asyncio
async def test_router_does_not_cache_failures(monkeypatch):
    class FailingService:
        async def search(self, _query):
            raise AgentPlannerError()

    monkeypatch.setattr(
        router_module,
        "AgentSearchService",
        lambda request: FailingService(),
    )
    await router_module.agent_search(SimpleNamespace(), "blue")

    assert agent_search_cache.get_by_query("blue") is None
