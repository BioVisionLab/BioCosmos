"""Tests for typed agent tool schemas and planner-call parsing."""

import json
from types import SimpleNamespace

import pytest

from app.configs.config import PromptsConfig
from app.services.agent_tools import (
    ColorArgs,
    CommonNameArgs,
    ImageSimilarityArgs,
    LocationArgs,
    TraitArgs,
    build_tool_definitions,
    build_tool_registry,
    parse_tool_calls,
)


def tool_call(name: str, arguments: str):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def test_tool_definitions_are_closed_and_server_owns_limits():
    prompts = PromptsConfig()
    registry = build_tool_registry(prompts)

    definitions = build_tool_definitions(prompts, registry)

    assert {item["function"]["name"] for item in definitions} == set(registry)
    assert all(
        item["function"]["parameters"]["additionalProperties"] is False
        for item in definitions
    )
    assert "limit" not in json.dumps(definitions)


def test_parse_tool_calls_validates_and_normalizes_location():
    prompts = PromptsConfig()
    registry = build_tool_registry(prompts)

    calls, warnings = parse_tool_calls(
        [tool_call("search_by_location", '{"country": "br"}')],
        registry,
    )

    assert warnings == []
    assert len(calls) == 1
    assert isinstance(calls[0].args, LocationArgs)
    assert calls[0].args.normalized_country() == "BR"
    assert calls[0].args.state_province is None


def test_parse_tool_calls_accepts_state_province():
    registry = build_tool_registry(PromptsConfig())

    calls, warnings = parse_tool_calls(
        [
            tool_call(
                "search_by_location",
                '{"country": "MY", "state_province": "  Sabah "}',
            )
        ],
        registry,
    )

    assert warnings == []
    args = calls[0].args
    assert isinstance(args, LocationArgs)
    assert args.normalized_country() == "MY"
    assert args.state_province == "Sabah"


@pytest.mark.parametrize(
    "arguments",
    [
        '{"location": "BR"}',
        '{"country": "BR", "state_province": ""}',
        '{"country": "BR", "county": "Manaus"}',
    ],
)
def test_parse_tool_calls_rejects_invalid_location_arguments(arguments):
    registry = build_tool_registry(PromptsConfig())

    calls, warnings = parse_tool_calls(
        [tool_call("search_by_location", arguments)], registry
    )

    assert calls == []
    assert [warning.code for warning in warnings] == ["invalid_tool_arguments"]


def test_parse_tool_calls_rejects_unknown_malformed_and_extra_arguments():
    prompts = PromptsConfig()
    registry = build_tool_registry(prompts)

    calls, warnings = parse_tool_calls(
        [
            tool_call("unknown", "{}"),
            tool_call("search_by_location", "[]"),
            tool_call(
                "search_by_color",
                '{"color_description": "blue", "limit": 999999}',
            ),
            tool_call("search_by_traits", "{}"),
        ],
        registry,
    )

    assert calls == []
    assert [warning.code for warning in warnings] == [
        "unknown_tool",
        "invalid_tool_arguments",
        "invalid_tool_arguments",
        "invalid_tool_arguments",
    ]


def test_parse_tool_calls_keeps_first_valid_duplicate():
    prompts = PromptsConfig()
    registry = build_tool_registry(prompts)

    calls, warnings = parse_tool_calls(
        [
            tool_call("search_by_color", '{"color_description": "blue"}'),
            tool_call("search_by_color", '{"color_description": "orange"}'),
        ],
        registry,
    )

    assert len(calls) == 1
    args = calls[0].args
    assert isinstance(args, ColorArgs)
    assert args.color_description == "blue"
    assert [warning.code for warning in warnings] == ["duplicate_tool_call"]


def test_common_names_pass_through_without_scientific_translation():
    registry = build_tool_registry(PromptsConfig())
    calls, warnings = parse_tool_calls(
        [
            tool_call("search_by_common_name", '{"common_name": "blue morpho"}'),
            tool_call("search_by_image_similarity", '{"reference_species": "monarch"}'),
        ],
        registry,
    )
    assert warnings == []
    assert calls[0].category == "filter"
    common_name_args = calls[0].args
    similarity_args = calls[1].args
    assert isinstance(common_name_args, CommonNameArgs)
    assert isinstance(similarity_args, ImageSimilarityArgs)
    assert common_name_args.common_name == "blue morpho"
    assert similarity_args.reference_species == "monarch"


def test_trait_args_accept_the_planner_s_casing():
    args = TraitArgs.model_validate(
        {
            "canopy": "Closed",
            "hostplant_family": "fabaceae",
            "flight_months": ["June", "JUL"],
        }
    )
    assert args.canopy == "closed"
    assert args.hostplant_family == "Fabaceae"
    assert args.flight_months == ["jun", "jul"]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        # The old graded vocabulary, which LepTraits never recorded.
        {"canopy_affinity": "High"},
        {"canopy": "high"},
        {"hostplant_family": "Fabaceae; DROP TABLE"},
        {"flight_months": ["summer"]},
        {"flight_months": []},
    ],
)
def test_trait_args_reject_unusable_values(arguments):
    with pytest.raises(ValueError):
        TraitArgs.model_validate(arguments)
