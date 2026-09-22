"""Send the planner request to each model and record what comes back."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from openai import AsyncOpenAI

from plannerbench.cases import Case
from plannerbench.scoring import RawToolCall, Trial, grade, plan_signature, validate_calls
from plannerbench.spec import PlannerSpec

MAX_ERROR_CHARACTERS = 300
MAX_CONTENT_CHARACTERS = 500


def make_client(base_url: str, api_key: str, *, max_retries: int = 0) -> Any:
    """An OpenAI-compatible async client.

    Retries default to off so a flaky model shows up as errors instead of as
    inflated latency.
    """
    return AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=max_retries)


def _request(spec: PlannerSpec, model: str, query: str, temperature: float | None) -> dict:
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": spec.system_prompt},
            {"role": "user", "content": query},
        ],
        "tools": spec.tools,
        "tool_choice": spec.tool_choice,
        "max_tokens": spec.max_tokens,
        "timeout": spec.timeout_seconds,
    }
    # The backend leaves temperature to the provider default, so only send one
    # when the benchmark is asked to.
    if temperature is not None:
        request["temperature"] = temperature
    return request


async def run_trial(
    client: Any,
    spec: PlannerSpec,
    case: Case,
    model: str,
    repeat: int,
    *,
    temperature: float | None = None,
) -> Trial:
    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            **_request(spec, model, case.query, temperature)
        )
    except Exception as exc:  # Every provider failure is a benchmark result.
        return Trial(
            model=model,
            case_id=case.id,
            repeat=repeat,
            status="error",
            error=f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARACTERS],
            latency_seconds=round(time.perf_counter() - started, 3),
        )
    latency = round(time.perf_counter() - started, 3)

    choices = getattr(response, "choices", None) or []
    if not choices:
        return Trial(
            model=model,
            case_id=case.id,
            repeat=repeat,
            status="error",
            error="response has no choices",
            latency_seconds=latency,
        )
    choice = choices[0]
    message = choice.message
    raw_calls = [
        RawToolCall(
            name=getattr(getattr(call, "function", None), "name", None),
            arguments=getattr(getattr(call, "function", None), "arguments", None),
        )
        for call in (getattr(message, "tool_calls", None) or [])
    ]
    calls = validate_calls(raw_calls, spec)
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
    content = getattr(message, "content", None)
    return Trial(
        model=model,
        case_id=case.id,
        repeat=repeat,
        status="ok",
        latency_seconds=latency,
        calls=calls,
        content=content[:MAX_CONTENT_CHARACTERS] if content else None,
        finish_reason=getattr(choice, "finish_reason", None),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        signature=plan_signature(calls),
        correct=grade(case, calls),
    )


async def run_benchmark(
    client: Any,
    spec: PlannerSpec,
    cases: list[Case],
    models: list[str],
    *,
    repeats: int,
    concurrency: int,
    temperature: float | None = None,
    on_trial: Callable[[Trial], None] | None = None,
) -> list[Trial]:
    """Run every (repeat, case, model) combination.

    Models are interleaved within each case and repeat, so load changes on a
    shared endpoint land on every model alike rather than on whichever ran last.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(case: Case, model: str, repeat: int) -> Trial:
        async with semaphore:
            trial = await run_trial(client, spec, case, model, repeat, temperature=temperature)
        if on_trial is not None:
            on_trial(trial)
        return trial

    jobs = [
        bounded(case, model, repeat)
        for repeat in range(1, repeats + 1)
        for case in cases
        for model in models
    ]
    trials = await asyncio.gather(*jobs)
    model_order = {model: index for index, model in enumerate(models)}
    case_order = {case.id: index for index, case in enumerate(cases)}
    return sorted(
        trials,
        key=lambda trial: (model_order[trial.model], case_order[trial.case_id], trial.repeat),
    )
