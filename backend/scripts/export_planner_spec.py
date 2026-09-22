"""
Export the agent-search planner spec for `plannerbench`.

The spec is exactly what the backend sends to the planner model: the router
system prompt, the tool definitions built from the typed argument models, and
the request settings. `plannerbench` replays it against other models, so the
benchmark measures the production prompt rather than a copy that can drift.

Usage:
    cd backend
    uv run python scripts/export_planner_spec.py
    uv run python scripts/export_planner_spec.py --output ../reports/planner/planner_spec.json
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.configs.config import OpenAIConfig, PromptsConfig
from app.services.agent import (
    PLANNER_MAX_TOKENS,
    PLANNER_TIMEOUT_SECONDS,
)
from app.services.agent_tools import (
    _compact_schema,
    build_tool_definitions,
    build_tool_registry,
)

SPEC_VERSION = 1
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2] / "reports" / "planner" / "planner_spec.json"
)


def build_spec() -> dict:
    prompts = PromptsConfig()
    registry = build_tool_registry(prompts)
    tools = build_tool_definitions(prompts, registry)
    system_prompt = prompts.router_agent

    validation_schemas = {}
    for spec in registry.values():
        schema = _compact_schema(spec.args_model.model_json_schema())
        if spec.name == "search_by_traits":
            # TraitArgs rejects an empty call in a pydantic validator, which
            # the JSON schema cannot express on its own.
            schema["minProperties"] = 1
        validation_schemas[spec.name] = schema

    fingerprint = hashlib.sha256(
        json.dumps(
            {"system_prompt": system_prompt, "tools": tools}, sort_keys=True
        ).encode()
    ).hexdigest()

    return {
        "spec_version": SPEC_VERSION,
        "system_prompt": system_prompt,
        "tools": tools,
        "tool_categories": {spec.name: spec.category for spec in registry.values()},
        "validation_schemas": validation_schemas,
        "tool_choice": "auto",
        "max_tokens": PLANNER_MAX_TOKENS,
        "timeout_seconds": PLANNER_TIMEOUT_SECONDS,
        "production_model": OpenAIConfig().model,
        "fingerprint": fingerprint,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the spec (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    spec = build_spec()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote planner spec ({len(spec['tools'])} tools) to {args.output}")


if __name__ == "__main__":
    main()
