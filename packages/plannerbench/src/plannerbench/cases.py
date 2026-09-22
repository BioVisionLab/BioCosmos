"""Labelled planner queries and the tool plans that count as correct for them."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

from harmonize_core.errors import ConfigurationError
from pydantic import BaseModel, Field, ValidationError, field_validator

from plannerbench.spec import PlannerSpec

ANY_VALUE = "*"

# One argument expectation: an exact value, any of several values, or ANY_VALUE
# for "present with any value". Comparison ignores case and outer whitespace.
ArgExpectation = str | list[str]
# tool name -> {argument -> expectation}. An empty mapping accepts any arguments.
# An empty plan ({}) means the planner should call no tool at all.
ExpectedPlan = dict[str, dict[str, ArgExpectation]]


class Case(BaseModel):
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    note: str = ""
    accept: list[ExpectedPlan] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _slug(cls, value: str) -> str:
        if value != value.strip() or " " in value:
            raise ValueError("case id must not contain spaces")
        return value


class CaseFile(BaseModel):
    cases: list[Case] = Field(min_length=1)


def load_cases(path: Path | None = None) -> list[Case]:
    """Load cases from TOML, defaulting to the packaged set."""
    try:
        if path is None:
            text = (
                resources.files("plannerbench.resources")
                .joinpath("cases.toml")
                .read_text(encoding="utf-8")
            )
            source = "packaged cases.toml"
        else:
            text = path.read_text(encoding="utf-8")
            source = str(path)
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Case file not found: {path}") from exc
    try:
        cases = CaseFile.model_validate(tomllib.loads(text)).cases
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(f"Invalid case file {source}: {exc}") from exc

    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise ConfigurationError(f"Duplicate case id in {source}: {case.id}")
        seen.add(case.id)
    return cases


def check_cases_against_spec(cases: list[Case], spec: PlannerSpec) -> None:
    """Fail early when a case expects a tool the planner is not offered."""
    for case in cases:
        for plan in case.accept:
            unknown = set(plan) - spec.tool_names
            if unknown:
                raise ConfigurationError(
                    f"Case '{case.id}' expects tools the spec does not define: {sorted(unknown)}"
                )
