"""Regression tests for agent-search orchestration and scoring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import polars as pl
import pytest
from app.configs.config import PromptsConfig
from app.services.agent import (
    MAX_RANKED_RESULTS,
    PAGE_SIZE,
    AgentConfigurationError,
    AgentSearchService,
    AgentToolFailureError,
)
from app.services.agent_tools import build_tool_registry
from app.services.gbif import GbifPersistData
from app.services.images import ImagePersistData
from openai import AuthenticationError, PermissionDeniedError


def tool_call(name: str, arguments: str):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def planner_response(*calls):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=list(calls)))]
    )


def make_service(*calls) -> AgentSearchService:
    service = AgentSearchService.__new__(AgentSearchService)
    service.tool_registry = build_tool_registry(PromptsConfig())
    service._plan = AsyncMock(return_value=planner_response(*calls))
    # Orchestration is under test here; linking to species pages has its own
    # tests below.
    service._link_species_pages = lambda dataframe: dataframe
    return service


def pages(available=True, keys=None):
    resolver = MagicMock()
    resolver.available.return_value = available
    resolver.page_keys_for_images.side_effect = lambda ids: {
        i: keys[i] for i in ids if i in (keys or {})
    }
    return resolver


def linking_service(resolver) -> AgentSearchService:
    service = AgentSearchService.__new__(AgentSearchService)
    service.species_pages = resolver
    return service


RANKED = pl.DataFrame(
    {
        "imgId": ["typo", "good", "orphan", "genus"],
        "species": ["vanessa_carduii", "vanessa_cardui", "bogus_name", "vanessa"],
        "score": [0.9, 0.8, 0.7, 0.6],
        "tool_names": [["search_by_color"]] * 4,
    }
)


def test_results_link_to_the_species_page_and_orphans_are_dropped():
    service = linking_service(
        pages(keys={"typo": "vanessa_cardui", "good": "vanessa_cardui"})
    )
    rows = service._link_species_pages(RANKED).to_dicts()
    # Two spellings of one species share a page; the higher-ranked stays.
    assert [(row["imgId"], row["speciesKey"]) for row in rows] == [
        ("typo", "vanessa_cardui")
    ]


def test_without_a_run_results_link_to_the_recorded_binomial():
    service = linking_service(pages(available=False))
    rows = service._link_species_pages(RANKED).to_dicts()
    assert [(row["imgId"], row["speciesKey"]) for row in rows] == [
        ("typo", "vanessa_carduii"),
        ("good", "vanessa_cardui"),
        ("orphan", "bogus_name"),
        ("genus", None),
    ]


def test_linking_an_empty_result_keeps_the_column():
    service = linking_service(pages())
    empty = AgentSearchService._empty_results()
    assert "speciesKey" in service._link_species_pages(empty).columns


@pytest.mark.asyncio
async def test_search_runs_filters_before_scoped_rankings():
    service = make_service(
        tool_call("search_by_color", '{"color_description": "blue"}'),
        tool_call("search_by_location", '{"country": "BR"}'),
    )
    executed = []

    async def execute(call, allowlist):
        executed.append((call.name, allowlist))
        if call.name == "search_by_location":
            return [
                {
                    "imgId": "filter-a",
                    "species": "Species a",
                    "tool_names": call.name,
                }
            ]
        return [
            {
                "imgId": "rank-a",
                "species": "Species a",
                "score": 0.8,
                "tool_names": call.name,
            }
        ]

    service._execute_tool = execute
    outcome = await service.search("blue butterflies in Brazil")

    assert executed == [
        ("search_by_location", None),
        ("search_by_color", {"Species a"}),
    ]
    assert outcome.warnings == []
    assert outcome.dataframe.to_dicts() == [
        {
            "imgId": "rank-a",
            "species": "Species a",
            "score": 0.8,
            "tool_names": ["search_by_color", "search_by_location"],
        }
    ]


@pytest.mark.asyncio
async def test_search_returns_partial_results_with_warning():
    service = make_service(
        tool_call("search_by_location", '{"country": "BR"}'),
        tool_call("search_by_color", '{"color_description": "blue"}'),
    )

    async def execute(call, allowlist):
        if call.name == "search_by_location":
            raise RuntimeError("database unavailable")
        assert allowlist is None
        return [
            {
                "imgId": "rank-a",
                "species": "Species a",
                "score": 0.75,
                "tool_names": call.name,
            }
        ]

    service._execute_tool = execute
    outcome = await service.search("blue butterflies in Brazil")

    assert outcome.dataframe["score"].to_list() == [0.75]
    assert [warning.code for warning in outcome.warnings] == ["tool_execution_failed"]
    assert outcome.warnings[0].tool == "search_by_location"


@pytest.mark.asyncio
async def test_search_falls_back_to_filters_when_all_rankings_fail():
    service = make_service(
        tool_call("search_by_location", '{"country": "BR"}'),
        tool_call("search_by_color", '{"color_description": "blue"}'),
    )

    async def execute(call, _allowlist):
        if call.name == "search_by_color":
            raise RuntimeError("vector unavailable")
        return [
            {
                "imgId": "filter-a",
                "species": "Species a",
                "tool_names": call.name,
            }
        ]

    service._execute_tool = execute
    outcome = await service.search("blue butterflies in Brazil")

    assert outcome.dataframe.to_dicts() == [
        {
            "imgId": "filter-a",
            "species": "Species a",
            "score": 1.0,
            "tool_names": ["search_by_location"],
        }
    ]
    assert outcome.warnings[0].tool == "search_by_color"


@pytest.mark.asyncio
async def test_search_does_not_fallback_when_ranking_succeeds_empty():
    service = make_service(
        tool_call("search_by_location", '{"country": "BR"}'),
        tool_call("search_by_color", '{"color_description": "blue"}'),
    )

    async def execute(call, _allowlist):
        if call.name == "search_by_color":
            return []
        return [
            {
                "imgId": "filter-a",
                "species": "Species a",
                "tool_names": call.name,
            }
        ]

    service._execute_tool = execute
    outcome = await service.search("blue butterflies in Brazil")

    assert outcome.dataframe.is_empty()
    assert outcome.warnings == []


@pytest.mark.asyncio
async def test_search_raises_when_every_tool_fails():
    service = make_service(
        tool_call("search_by_color", '{"color_description": "blue"}')
    )

    async def execute(_call, _allowlist):
        raise RuntimeError("vector unavailable")

    service._execute_tool = execute

    with pytest.raises(AgentToolFailureError):
        await service.search("blue butterflies")


def test_ranking_scores_scale_against_the_retrieved_pool():
    rows = AgentSearchService._build_ranking_rows(
        pl.DataFrame(
            {
                "imgId": ["a", "b", "c"],
                "species": ["A", "B", "C"],
                "distance": [0.2, 1.0, 1.5],
            }
        ),
        tool_name="search_by_color",
    )

    # Nearest candidate is full confidence, furthest sits on the floor, and
    # distances past 1.0 stay ordered instead of collapsing to a flat 0.0.
    assert [row["score"] for row in rows] == pytest.approx([1.0, 0.6923077, 0.5])


def test_ranking_scores_stay_high_for_uniform_distances():
    rows = AgentSearchService._build_ranking_rows(
        pl.DataFrame(
            {
                "imgId": ["a", "b"],
                "species": ["A", "B"],
                "distance": [0.8, 0.8],
            }
        ),
        tool_name="search_by_color",
    )

    assert [row["score"] for row in rows] == pytest.approx([1.0, 1.0])


def test_aggregation_keeps_ranked_list_beyond_one_page():
    rows = [
        {
            "imgId": f"img-{index:04d}",
            "species": f"Species {index:04d}",
            "score": 1.0 - index / 10_000,
            "tool_names": "search_by_color",
        }
        for index in range(MAX_RANKED_RESULTS + 20)
    ]

    dataframe = AgentSearchService._aggregate_ranking_results(
        rows, filter_tool_names=[]
    )

    # Later pages are served from this list, so it must not stop at one page.
    assert dataframe.height == MAX_RANKED_RESULTS
    assert dataframe["species"][0] == "Species 0000"


def test_single_ranking_tool_match_keeps_full_score():
    dataframe = AgentSearchService._aggregate_ranking_results(
        [
            {
                "imgId": "a",
                "species": "Species a",
                "score": 0.9,
                "tool_names": "search_by_color",
            },
            {
                "imgId": "b",
                "species": "Species b",
                "score": 0.8,
                "tool_names": "search_by_color",
            },
            {
                "imgId": "c",
                "species": "Species b",
                "score": 0.7,
                "tool_names": "search_by_image_similarity",
            },
        ],
        filter_tool_names=[],
    )

    scores = {row["species"]: row["score"] for row in dataframe.to_dicts()}
    # Species a was ranked by one tool only and keeps that tool's confidence
    # instead of being halved by the tool it never matched.
    assert scores["Species a"] == pytest.approx(0.9)
    assert scores["Species b"] == pytest.approx(0.75)


def test_aggregation_averages_rankers_and_selects_best_image():
    dataframe = AgentSearchService._aggregate_ranking_results(
        [
            {
                "imgId": "z",
                "species": "Species a",
                "score": 0.8,
                "tool_names": "search_by_color",
            },
            {
                "imgId": "a",
                "species": "Species a",
                "score": 0.6,
                "tool_names": "search_by_image_similarity",
            },
        ],
        filter_tool_names=["search_by_location"],
    )

    row = dataframe.to_dicts()[0]
    assert row["imgId"] == "z"
    assert row["species"] == "Species a"
    assert row["score"] == pytest.approx(0.7)
    assert row["tool_names"] == [
        "search_by_color",
        "search_by_image_similarity",
        "search_by_location",
    ]


def test_embedding_query_applies_escaped_allowlist_prefilter():
    class FakeSearch:
        def __init__(self):
            self.where_clause = None

        def distance_type(self, _distance_type):
            return self

        def nprobes(self, _n):
            return self

        def refine_factor(self, _n):
            return self

        def select(self, columns):
            assert columns == ["img_id"]
            return self

        def where(self, clause, *, prefilter):
            assert prefilter is True
            self.where_clause = clause
            return self

        def limit(self, value):
            assert value == 10
            return self

        def to_polars(self):
            return pl.DataFrame({"img_id": ["image-a"], "_distance": [0.2]})

    search = FakeSearch()
    table = SimpleNamespace(search=lambda *_args, **_kwargs: search)
    image_service = ImagePersistData.__new__(ImagePersistData)
    image_service.db_table = table
    image_service.logger = MagicMock()

    result = image_service._query_embedding(
        query_vector=[],
        vector_column_name="unicom_embeddings",
        limit=10,
        filter_img_ids=["safe", "quote'id"],
    )

    assert search.where_clause == "img_id IN ('safe', 'quote''id')"
    assert result.to_dicts() == [{"imgId": "image-a", "distance": 0.2}]


def test_country_code_search_uses_bound_parameters():
    gbif = GbifPersistData.__new__(GbifPersistData)
    gbif.table_name = "gbif_meta"
    gbif.db_client = MagicMock()
    gbif.db_client.execute_prepared_to_pl.return_value = pl.DataFrame(
        {"species": ["Species a"]}
    )

    result = gbif.search_by_country_code("br", limit=25)

    sql, params = gbif.db_client.execute_prepared_to_pl.call_args.args
    assert "UPPER(countryCode) = ?" in sql
    assert "BR" not in sql
    assert params == ["BR", 25]
    assert result == ["Species a"]


def _similarity_service(species_ids, genus_ids):
    service = AgentSearchService.__new__(AgentSearchService)
    service.common_name_search = MagicMock()
    service.common_name_search.search.return_value = []
    service.image_meta_service = MagicMock()
    service.image_meta_service.get_image_ids_by_species.return_value = species_ids
    service.image_meta_service.get_image_ids_by_genus.return_value = genus_ids
    service.image_service = MagicMock()
    service.image_service.find_similar_images.return_value = pl.DataFrame(
        {
            "imgId": ["img-a", "img-b"],
            "species": ["caligo_eurilochus", "opsiphanes_invirae"],
            "distance": [0.1, 0.3],
        }
    )
    return service


@pytest.mark.asyncio
async def test_image_similarity_falls_back_to_genus_reference():
    service = _similarity_service(species_ids=[], genus_ids=["ref-1", "ref-2"])

    rows = await service._search_by_image_similarity("Caligo", None)

    service.image_meta_service.get_image_ids_by_genus.assert_called_once()
    call = service.image_service.find_similar_images.call_args
    assert call.args[0] == ["ref-1", "ref-2"]
    # The genus's own species are what a descriptive query is after.
    assert call.kwargs["exclude_species"] is None
    assert [row["species"] for row in rows] == [
        "caligo_eurilochus",
        "opsiphanes_invirae",
    ]


@pytest.mark.asyncio
async def test_image_similarity_excludes_exact_reference_species():
    service = _similarity_service(species_ids=["ref-1"], genus_ids=[])

    await service._search_by_image_similarity("Caligo eurilochus", None)

    service.image_meta_service.get_image_ids_by_genus.assert_not_called()
    kwargs = service.image_service.find_similar_images.call_args.kwargs
    assert kwargs["exclude_species"] == "Caligo eurilochus"
    assert kwargs["min_species"] == PAGE_SIZE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "calls",
    [(), (tool_call("search_by_location", '{"country": "Brazil"}'),)],
    ids=["no-tools", "only-invalid-tools"],
)
async def test_search_falls_back_to_text_search_without_usable_tools(calls):
    service = make_service(*calls)
    executed = []

    async def execute(call, allowlist):
        executed.append((call.name, call.args.model_dump(), allowlist))
        return [
            {
                "imgId": "rank-a",
                "species": "Species a",
                "score": 0.9,
                "tool_names": call.name,
            }
        ]

    service._execute_tool = execute
    outcome = await service.search("owl-like butterfly")

    assert executed == [
        ("search_by_color", {"color_description": "owl-like butterfly"}, None)
    ]
    assert outcome.dataframe["species"].to_list() == ["Species a"]


@pytest.mark.asyncio
async def test_common_name_filter_scopes_ranking_and_reports_both_functions():
    service = make_service(
        tool_call("search_by_common_name", '{"common_name": "monarch"}'),
        tool_call("search_by_color", '{"color_description": "orange"}'),
    )
    service.common_name_search = MagicMock()
    service.common_name_search.search.return_value = ["danaus_plexippus"]
    service.image_meta_service = MagicMock()
    service.image_meta_service.get_species_first_image_ids.return_value = pl.DataFrame(
        {"imgId": ["ref"], "species": ["danaus_plexippus"]}
    )
    service._search_by_color = AsyncMock(
        return_value=[
            {
                "imgId": "rank",
                "species": "danaus_plexippus",
                "score": 0.8,
                "tool_names": "search_by_color",
            }
        ]
    )
    outcome = await service.search("orange monarch")
    service.common_name_search.search.assert_called_once_with("monarch")
    service._search_by_color.assert_awaited_once_with("orange", {"danaus_plexippus"})
    assert outcome.dataframe["tool_names"].to_list() == [
        ["search_by_color", "search_by_common_name"]
    ]


@pytest.mark.asyncio
async def test_unmatched_common_name_never_falls_back_to_visual_search():
    service = make_service(
        tool_call("search_by_common_name", '{"common_name": "unknown"}'),
        tool_call("search_by_color", '{"color_description": "blue"}'),
    )
    service.common_name_search = MagicMock()
    service.common_name_search.search.return_value = []
    service._search_by_color = AsyncMock()
    outcome = await service.search("blue unknown")
    assert outcome.dataframe.is_empty()
    service._search_by_color.assert_not_awaited()


@pytest.mark.asyncio
async def test_similarity_resolves_all_common_name_references():
    service = _similarity_service(species_ids=[], genus_ids=[])
    service.common_name_search.search.return_value = ["species_a", "species_b"]
    service.image_meta_service.get_image_ids_by_species.side_effect = [
        [],
        ["a", "shared"],
        ["b", "shared"],
    ]
    await service._search_by_image_similarity("shared common name", None)
    service.common_name_search.search.assert_called_once_with("shared common name")
    call = service.image_service.find_similar_images.call_args
    assert call.args[0] == ["a", "b", "shared"]
    assert call.kwargs["exclude_species"] == ["species_a", "species_b"]
    service.image_meta_service.get_image_ids_by_genus.assert_not_called()


@pytest.mark.asyncio
async def test_unmatched_similarity_reference_returns_no_matches():
    service = _similarity_service(species_ids=[], genus_ids=[])
    assert await service._search_by_image_similarity("unknown butterfly", None) == []
    service.image_service.find_similar_images.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "status"),
    [(AuthenticationError, 401), (PermissionDeniedError, 403)],
)
async def test_planner_access_failure_returns_safe_configuration_error(
    error_type, status
):
    import json
    from unittest.mock import patch

    from app.routers import agent_search as router_module

    response = httpx.Response(
        status, request=httpx.Request("POST", "https://provider.test")
    )
    provider_error = error_type("private provider detail", response=response, body=None)
    service = AgentSearchService.__new__(AgentSearchService)
    service.client = MagicMock()
    service.client.chat.completions.create.side_effect = provider_error
    service.model = "configured-model"
    service.system_prompt = "Search species"
    service.tool_definitions = []

    with pytest.raises(AgentConfigurationError):
        await service._plan("blue butterfly")

    with patch.object(router_module, "AgentSearchService", return_value=service):
        result = await router_module.agent_search(SimpleNamespace(), "blue butterfly")
    assert result.status_code == 503
    error = json.loads(result.body)["error"]
    assert "configured model access" in error
    assert "private provider detail" not in error
