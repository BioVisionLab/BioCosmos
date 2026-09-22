from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from plannerbench.spec import PlannerSpec

TRAIT = {"anyOf": [{"enum": ["High", "Medium", "Low"], "type": "string"}, {"type": "null"}]}

SCHEMAS: dict[str, dict[str, Any]] = {
    "search_by_common_name": {
        "additionalProperties": False,
        "properties": {"common_name": {"maxLength": 200, "minLength": 1, "type": "string"}},
        "required": ["common_name"],
        "type": "object",
    },
    "search_by_color": {
        "additionalProperties": False,
        "properties": {"color_description": {"maxLength": 200, "minLength": 1, "type": "string"}},
        "required": ["color_description"],
        "type": "object",
    },
    "search_by_location": {
        "additionalProperties": False,
        "properties": {"location": {"pattern": "^[A-Za-z]{2}$", "type": "string"}},
        "required": ["location"],
        "type": "object",
    },
    "search_by_image_similarity": {
        "additionalProperties": False,
        "properties": {"reference_species": {"maxLength": 128, "minLength": 1, "type": "string"}},
        "required": ["reference_species"],
        "type": "object",
    },
    "search_by_traits": {
        "additionalProperties": False,
        "minProperties": 1,
        "properties": {
            "canopy_affinity": TRAIT,
            "edge_affinity": TRAIT,
            "moisture_affinity": TRAIT,
            "disturbance_affinity": TRAIT,
        },
        "type": "object",
    },
}
CATEGORIES = {
    "search_by_common_name": "filter",
    "search_by_color": "ranking",
    "search_by_image_similarity": "ranking",
    "search_by_location": "filter",
    "search_by_traits": "filter",
}


def spec_payload() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "system_prompt": "You are a search router.",
        "tools": [
            {"type": "function", "function": {"name": name, "description": name, "parameters": s}}
            for name, s in SCHEMAS.items()
        ],
        "tool_categories": CATEGORIES,
        "validation_schemas": SCHEMAS,
        "tool_choice": "auto",
        "max_tokens": 512,
        "timeout_seconds": 30.0,
        "production_model": "mistral-small-3.1",
        "fingerprint": "f" * 64,
    }


@pytest.fixture
def spec() -> PlannerSpec:
    return PlannerSpec.model_validate(spec_payload())


@pytest.fixture
def spec_file(tmp_path: Path) -> Path:
    path = tmp_path / "planner_spec.json"
    path.write_text(json.dumps(spec_payload()), encoding="utf-8")
    return path


def response(*calls: tuple[str, str], content: str | None = None) -> SimpleNamespace:
    """A chat-completions response carrying the given (name, arguments) tool calls."""
    message = SimpleNamespace(
        content=content,
        tool_calls=[
            SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
            for name, arguments in calls
        ]
        or None,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )


class FakeClient:
    """Serves scripted responses keyed by (model, user query)."""

    def __init__(self, script: dict[tuple[str, str], Any]):
        self.script = script
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **request: Any) -> Any:
        self.requests.append(request)
        outcome = self.script[(request["model"], request["messages"][-1]["content"])]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
