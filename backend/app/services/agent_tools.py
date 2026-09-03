"""Typed definitions and parsing helpers for agent search tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..configs.config import PromptsConfig


ToolCategory = Literal["filter", "ranking"]


class ToolArgs(BaseModel):
    """Base model for arguments produced by the routing model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ImageSimilarityArgs(ToolArgs):
    reference_species: str = Field(min_length=1, max_length=128)


class LocationArgs(ToolArgs):
    location: str = Field(pattern=r"^[A-Za-z]{2}$")

    def normalized_location(self) -> str:
        return self.location.upper()


class ColorArgs(ToolArgs):
    color_description: str = Field(min_length=1, max_length=200)


TraitValue = Literal["High", "Medium", "Low"]


class TraitArgs(ToolArgs):
    canopy_affinity: TraitValue | None = None
    edge_affinity: TraitValue | None = None
    moisture_affinity: TraitValue | None = None
    disturbance_affinity: TraitValue | None = None

    @model_validator(mode="after")
    def require_trait(self) -> "TraitArgs":
        if not any(
            (
                self.canopy_affinity,
                self.edge_affinity,
                self.moisture_affinity,
                self.disturbance_affinity,
            )
        ):
            raise ValueError("At least one trait affinity is required.")
        return self


@dataclass(frozen=True)
class ToolSpec:
    name: str
    category: ToolCategory
    args_model: type[ToolArgs]
    prompt_path: str


@dataclass(frozen=True)
class ParsedToolCall:
    name: str
    category: ToolCategory
    args: ToolArgs


class AgentWarning(BaseModel):
    code: str
    message: str
    tool: str | None = None


def _compact_schema(value: Any) -> Any:
    """Remove schema metadata that costs tokens but does not guide arguments."""
    if isinstance(value, dict):
        return {
            key: _compact_schema(item)
            for key, item in value.items()
            if key not in {"title", "default"}
        }
    if isinstance(value, list):
        return [_compact_schema(item) for item in value]
    return value


def build_tool_registry(prompts: PromptsConfig) -> dict[str, ToolSpec]:
    specs = (
        ToolSpec(
            "search_by_image_similarity",
            "ranking",
            ImageSimilarityArgs,
            prompts.image_similarity,
        ),
        ToolSpec(
            "search_by_location",
            "filter",
            LocationArgs,
            prompts.location_search,
        ),
        ToolSpec(
            "search_by_color",
            "ranking",
            ColorArgs,
            prompts.color_search,
        ),
        ToolSpec(
            "search_by_traits",
            "filter",
            TraitArgs,
            prompts.trait_search,
        ),
    )
    return {spec.name: spec for spec in specs}


def build_tool_definitions(
    prompts: PromptsConfig, registry: dict[str, ToolSpec]
) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for spec in registry.values():
        schema = _compact_schema(spec.args_model.model_json_schema())
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": prompts.load_tool_description(spec.prompt_path),
                    "parameters": schema,
                },
            }
        )
    return definitions


def parse_tool_calls(
    raw_tool_calls: list[Any], registry: dict[str, ToolSpec]
) -> tuple[list[ParsedToolCall], list[AgentWarning]]:
    parsed: list[ParsedToolCall] = []
    warnings: list[AgentWarning] = []
    seen_names: set[str] = set()

    for raw_call in raw_tool_calls:
        function = getattr(raw_call, "function", None)
        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)

        if not isinstance(name, str):
            warnings.append(
                AgentWarning(
                    code="unknown_tool",
                    tool=None,
                    message="The planner selected an unsupported search tool.",
                )
            )
            continue

        spec = registry.get(name)
        if spec is None:
            warnings.append(
                AgentWarning(
                    code="unknown_tool",
                    tool=name,
                    message="The planner selected an unsupported search tool.",
                )
            )
            continue
        if name in seen_names:
            warnings.append(
                AgentWarning(
                    code="duplicate_tool_call",
                    tool=name,
                    message="A duplicate tool call was ignored.",
                )
            )
            continue

        try:
            if not isinstance(arguments, str):
                raise ValueError("Tool arguments must be a JSON string.")
            decoded = json.loads(arguments)
            if not isinstance(decoded, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            validated = spec.args_model.model_validate(decoded)
        except (json.JSONDecodeError, TypeError, ValidationError, ValueError):
            warnings.append(
                AgentWarning(
                    code="invalid_tool_arguments",
                    tool=name,
                    message="The planner produced invalid arguments for this tool.",
                )
            )
            continue

        seen_names.add(name)
        parsed.append(
            ParsedToolCall(
                name=name,
                category=spec.category,
                args=validated,
            )
        )

    return parsed, warnings
