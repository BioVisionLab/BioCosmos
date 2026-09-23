"""Send the planner request to each model and record what comes back."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from plannerbench.cases import Case
from plannerbench.scoring import RawToolCall, Trial, grade, plan_signature, validate_calls
from plannerbench.spec import PlannerSpec

MAX_ERROR_CHARACTERS = 300
MAX_CONTENT_CHARACTERS = 500
DEFAULT_REQUESTS_PER_MINUTE = 100.0
DEFAULT_RATE_LIMIT_RETRIES = 3
MAX_BACKOFF_SECONDS = 30.0


class RequestPacer:
    """Space request starts evenly to stay under a requests-per-minute limit.

    Even spacing, rather than a sliding window, never sends a burst, so it also
    holds on gateways that enforce the limit over shorter intervals.
    """

    def __init__(
        self, requests_per_minute: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.interval = 60.0 / requests_per_minute
        self._clock = clock
        self._next_start: float | None = None

    async def acquire(self) -> None:
        # No await before the slot is claimed, so concurrent callers on the
        # event loop each get a distinct start time.
        now = self._clock()
        start = now if self._next_start is None else max(now, self._next_start)
        self._next_start = start + self.interval
        if start > now:
            await asyncio.sleep(start - now)


def _retry_after(exc: RateLimitError, attempt: int) -> float:
    """Seconds to wait before retrying a 429: ``Retry-After`` or exponential backoff."""
    header = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        if header is not None:
            return min(max(float(header), 0.0), MAX_BACKOFF_SECONDS)
    except ValueError:  # An HTTP date; fall back to backoff.
        pass
    return min(2.0 * 2**attempt, MAX_BACKOFF_SECONDS)


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
    pacer: RequestPacer | None = None,
    rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
) -> Trial:
    """Run one planner call.

    A 429 is a quota problem, not a model result, so it is retried up to
    ``rate_limit_retries`` times. Latency covers only the final attempt.
    """
    retries = 0
    while True:
        if pacer is not None:
            await pacer.acquire()
        started = time.perf_counter()
        try:
            response = await client.chat.completions.create(
                **_request(spec, model, case.query, temperature)
            )
            break
        except Exception as exc:  # Every provider failure is a benchmark result.
            if isinstance(exc, RateLimitError) and retries < rate_limit_retries:
                await asyncio.sleep(_retry_after(exc, retries))
                retries += 1
                continue
            return Trial(
                model=model,
                case_id=case.id,
                repeat=repeat,
                status="error",
                error=f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARACTERS],
                latency_seconds=round(time.perf_counter() - started, 3),
                rate_limit_retries=retries,
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
            rate_limit_retries=retries,
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
        rate_limit_retries=retries,
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
    requests_per_minute: float | None = DEFAULT_REQUESTS_PER_MINUTE,
    rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
    on_trial: Callable[[Trial], None] | None = None,
) -> list[Trial]:
    """Run every (repeat, case, model) combination.

    Models are interleaved within each case and repeat, so load changes on a
    shared endpoint land on every model alike rather than on whichever ran last.
    ``concurrency`` caps calls in flight; ``requests_per_minute`` caps how fast
    calls start across all of them (``None`` or 0 disables pacing).
    """
    semaphore = asyncio.Semaphore(concurrency)
    pacer = RequestPacer(requests_per_minute) if requests_per_minute else None

    async def bounded(case: Case, model: str, repeat: int) -> Trial:
        async with semaphore:
            trial = await run_trial(
                client,
                spec,
                case,
                model,
                repeat,
                temperature=temperature,
                pacer=pacer,
                rate_limit_retries=rate_limit_retries,
            )
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
