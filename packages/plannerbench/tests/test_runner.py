from __future__ import annotations

import asyncio

import httpx
import pytest
from conftest import FakeClient, response
from openai import RateLimitError

from plannerbench.cases import Case
from plannerbench.runner import RequestPacer, run_benchmark, run_trial
from plannerbench.spec import PlannerSpec

CASE = Case(
    id="similar",
    query="monarch look-alikes",
    accept=[{"search_by_image_similarity": {"reference_species": "Danaus plexippus"}}],
)
GOOD = response(("search_by_image_similarity", '{"reference_species": "Danaus plexippus"}'))


def rate_limited(retry_after: str | None = "1") -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    return RateLimitError(
        "Rate limit exceeded",
        response=httpx.Response(429, headers=headers, request=request),
        body=None,
    )


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return recorded


def test_pacer_spaces_request_starts_evenly(sleeps: list[float]) -> None:
    pacer = RequestPacer(120, clock=lambda: 10.0)

    async def acquire_all() -> None:
        await asyncio.gather(*(pacer.acquire() for _ in range(5)))

    asyncio.run(acquire_all())
    assert sleeps == [0.5, 1.0, 1.5, 2.0]


def test_pacer_does_not_wait_once_the_interval_has_passed(sleeps: list[float]) -> None:
    now = [0.0]
    pacer = RequestPacer(60, clock=lambda: now[0])

    async def two_calls() -> None:
        await pacer.acquire()
        now[0] = 5.0
        await pacer.acquire()

    asyncio.run(two_calls())
    assert sleeps == []


def test_rate_limit_is_retried_after_retry_after(spec: PlannerSpec, sleeps: list[float]) -> None:
    client = FakeClient({("m", CASE.query): [rate_limited("1"), GOOD]})
    trial = asyncio.run(run_trial(client, spec, CASE, "m", 1))
    assert trial.status == "ok" and trial.correct
    assert trial.rate_limit_retries == 1
    assert sleeps == [1.0]
    assert len(client.requests) == 2


def test_rate_limit_without_header_backs_off_exponentially(
    spec: PlannerSpec, sleeps: list[float]
) -> None:
    client = FakeClient({("m", CASE.query): [rate_limited(None), rate_limited(None), GOOD]})
    trial = asyncio.run(run_trial(client, spec, CASE, "m", 1))
    assert trial.status == "ok"
    assert sleeps == [2.0, 4.0]


def test_rate_limit_becomes_an_error_when_retries_run_out(
    spec: PlannerSpec, sleeps: list[float]
) -> None:
    client = FakeClient({("m", CASE.query): [rate_limited() for _ in range(3)]})
    trial = asyncio.run(run_trial(client, spec, CASE, "m", 1, rate_limit_retries=2))
    assert trial.status == "error" and "RateLimitError" in (trial.error or "")
    assert trial.rate_limit_retries == 2
    assert len(client.requests) == 3


def test_other_errors_are_not_retried(spec: PlannerSpec, sleeps: list[float]) -> None:
    client = FakeClient({("m", CASE.query): [TimeoutError("slow"), GOOD]})
    trial = asyncio.run(run_trial(client, spec, CASE, "m", 1))
    assert trial.status == "error" and trial.rate_limit_retries == 0
    assert sleeps == [] and len(client.requests) == 1


def test_benchmark_paces_every_call(spec: PlannerSpec, sleeps: list[float]) -> None:
    client = FakeClient({("m", CASE.query): GOOD})
    trials = asyncio.run(
        run_benchmark(client, spec, [CASE], ["m"], repeats=4, concurrency=4, requests_per_minute=60)
    )
    assert len(trials) == 4
    assert len(sleeps) == 3 and all(0 < seconds <= 3.0 for seconds in sleeps)
