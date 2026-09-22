"""Validate planner tool calls, grade them against cases, and summarize models."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel

from plannerbench.cases import ANY_VALUE, Case, ExpectedPlan
from plannerbench.spec import PlannerSpec


class RawToolCall(BaseModel):
    name: str | None
    arguments: str | None


class ToolCallRecord(BaseModel):
    name: str | None
    raw_arguments: str | None
    arguments: dict[str, Any] | None = None
    valid: bool
    error: str | None = None


class Trial(BaseModel):
    model: str
    case_id: str
    repeat: int
    status: Literal["ok", "error"]
    error: str | None = None
    latency_seconds: float | None = None
    calls: list[ToolCallRecord] = []
    content: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    signature: str | None = None
    correct: bool = False


class ModelSummary(BaseModel):
    model: str
    trials: int
    api_errors: int
    correct: int
    accuracy: float
    consistent_cases: int
    case_count: int
    no_tool_rate: float
    invalid_call_rate: float
    latency_p50_seconds: float | None
    latency_p95_seconds: float | None
    latency_max_seconds: float | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    per_case_correct: dict[str, int]


def validate_calls(raw_calls: Iterable[RawToolCall], spec: PlannerSpec) -> list[ToolCallRecord]:
    """Apply the backend's acceptance rules to one planner response.

    Mirrors ``parse_tool_calls``: unknown tools, undecodable or schema-invalid
    arguments, and repeat calls to a tool are all rejected. String values are
    trimmed and nulls dropped first, as the pydantic argument models do.
    """
    records: list[ToolCallRecord] = []
    seen: set[str] = set()
    for raw in raw_calls:
        name, text = raw.name, raw.arguments
        if name is None or name not in spec.tool_names:
            records.append(_invalid(name, text, "unknown tool"))
            continue
        if name in seen:
            records.append(_invalid(name, text, "duplicate tool call"))
            continue
        try:
            decoded = json.loads(text) if isinstance(text, str) else None
        except json.JSONDecodeError:
            records.append(_invalid(name, text, "arguments are not valid JSON"))
            continue
        if not isinstance(decoded, dict):
            records.append(_invalid(name, text, "arguments are not a JSON object"))
            continue
        arguments = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in decoded.items()
            if value is not None
        }
        errors = sorted(
            Draft202012Validator(spec.validation_schemas[name]).iter_errors(arguments),
            key=lambda error: list(error.path),
        )
        if errors:
            records.append(_invalid(name, text, errors[0].message))
            continue
        seen.add(name)
        records.append(
            ToolCallRecord(name=name, raw_arguments=text, arguments=arguments, valid=True)
        )
    return records


def _invalid(name: str | None, text: str | None, reason: str) -> ToolCallRecord:
    return ToolCallRecord(name=name, raw_arguments=text, valid=False, error=reason)


def _normalize(value: Any) -> str:
    return " ".join(str(value).split()).lower()


def plan_signature(calls: Iterable[ToolCallRecord]) -> str:
    """Canonical form of the accepted calls, for comparing repeats."""
    plan = {
        call.name: {key: _normalize(value) for key, value in (call.arguments or {}).items()}
        for call in calls
        if call.valid and call.name
    }
    return json.dumps(plan, sort_keys=True)


def matches_plan(calls: Iterable[ToolCallRecord], plan: ExpectedPlan) -> bool:
    accepted = {call.name: call.arguments or {} for call in calls if call.valid and call.name}
    if set(accepted) != set(plan):
        return False
    for tool, expectations in plan.items():
        arguments = accepted[tool]
        for key, expected in expectations.items():
            if key not in arguments:
                return False
            if expected == ANY_VALUE:
                continue
            options = expected if isinstance(expected, list) else [expected]
            if _normalize(arguments[key]) not in {_normalize(option) for option in options}:
                return False
    return True


def grade(case: Case, calls: list[ToolCallRecord]) -> bool:
    return any(matches_plan(calls, plan) for plan in case.accept)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return round(ordered[index], 3)


def summarize(trials: list[Trial], models: list[str], cases: list[Case]) -> list[ModelSummary]:
    """One summary per model, in the order the models were requested.

    Accuracy is over every trial, so an API error counts as a miss. A case is
    consistent when every repeat succeeded and produced the same accepted plan.
    """
    by_model: dict[str, list[Trial]] = defaultdict(list)
    for trial in trials:
        by_model[trial.model].append(trial)

    summaries: list[ModelSummary] = []
    for model in models:
        model_trials = by_model.get(model, [])
        ok_trials = [trial for trial in model_trials if trial.status == "ok"]
        all_calls = [call for trial in ok_trials for call in trial.calls]
        latencies = [
            trial.latency_seconds for trial in ok_trials if trial.latency_seconds is not None
        ]

        per_case: dict[str, list[Trial]] = defaultdict(list)
        for trial in model_trials:
            per_case[trial.case_id].append(trial)
        consistent = sum(
            1
            for case in cases
            if per_case[case.id]
            and all(trial.status == "ok" for trial in per_case[case.id])
            and len({trial.signature for trial in per_case[case.id]}) == 1
        )
        correct = sum(trial.correct for trial in model_trials)

        summaries.append(
            ModelSummary(
                model=model,
                trials=len(model_trials),
                api_errors=len(model_trials) - len(ok_trials),
                correct=correct,
                accuracy=round(correct / len(model_trials), 4) if model_trials else 0.0,
                consistent_cases=consistent,
                case_count=len(cases),
                no_tool_rate=round(
                    sum(not any(call.valid for call in trial.calls) for trial in ok_trials)
                    / len(ok_trials),
                    4,
                )
                if ok_trials
                else 0.0,
                invalid_call_rate=round(
                    sum(not call.valid for call in all_calls) / len(all_calls), 4
                )
                if all_calls
                else 0.0,
                latency_p50_seconds=_percentile(latencies, 0.5),
                latency_p95_seconds=_percentile(latencies, 0.95),
                latency_max_seconds=round(max(latencies), 3) if latencies else None,
                prompt_tokens=sum(trial.prompt_tokens or 0 for trial in ok_trials),
                completion_tokens=sum(trial.completion_tokens or 0 for trial in ok_trials),
                total_tokens=sum(
                    trial.total_tokens
                    if trial.total_tokens is not None
                    else (trial.prompt_tokens or 0) + (trial.completion_tokens or 0)
                    for trial in ok_trials
                ),
                per_case_correct={
                    case.id: sum(trial.correct for trial in per_case[case.id]) for case in cases
                },
            )
        )
    return summaries
