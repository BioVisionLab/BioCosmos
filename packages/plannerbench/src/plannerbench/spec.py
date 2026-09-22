"""The planner request the backend makes, as exported by the backend itself."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from harmonize_core.errors import ConfigurationError
from pydantic import BaseModel, ValidationError

SUPPORTED_SPEC_VERSION = 1
DEFAULT_SPEC_PATH = Path("reports") / "planner" / "planner_spec.json"
EXPORT_HINT = "cd backend && uv run python scripts/export_planner_spec.py"


class PlannerSpec(BaseModel):
    """System prompt, tool definitions, and request settings for one planner call.

    Written by ``backend/scripts/export_planner_spec.py`` so the benchmark replays
    the production prompt instead of a hand-maintained copy.
    """

    spec_version: int
    system_prompt: str
    tools: list[dict[str, Any]]
    tool_categories: dict[str, Literal["filter", "ranking"]]
    validation_schemas: dict[str, dict[str, Any]]
    tool_choice: str = "auto"
    max_tokens: int = 512
    timeout_seconds: float = 30.0
    production_model: str | None = None
    fingerprint: str

    @property
    def tool_names(self) -> set[str]:
        return set(self.tool_categories)


def load_spec(path: Path) -> PlannerSpec:
    if not path.exists():
        raise ConfigurationError(
            f"Planner spec not found: {path}. Export it first with: {EXPORT_HINT}"
        )
    try:
        spec = PlannerSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid planner spec {path}: {exc}") from exc
    if spec.spec_version != SUPPORTED_SPEC_VERSION:
        raise ConfigurationError(
            f"Unsupported planner spec version {spec.spec_version}; "
            f"expected {SUPPORTED_SPEC_VERSION}. Re-export it with: {EXPORT_HINT}"
        )
    missing = spec.tool_names - set(spec.validation_schemas)
    if missing:
        raise ConfigurationError(f"Planner spec lacks validation schemas for: {sorted(missing)}")
    return spec
