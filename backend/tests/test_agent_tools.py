"""Tests for typed agent tool schemas and planner-call parsing."""

import json
from types import SimpleNamespace

from app.configs.config import PromptsConfig
from app.services.agent_tools import (
    LocationArgs,
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
        [tool_call("search_by_location", '{"location": "br"}')],
        registry,
    )

    assert warnings == []
    assert len(calls) == 1
    assert isinstance(calls[0].args, LocationArgs)
    assert calls[0].args.normalized_location() == "BR"


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
    assert calls[0].args.color_description == "blue"
    assert [warning.code for warning in warnings] == ["duplicate_tool_call"]
