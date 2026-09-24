from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from conftest import FakeClient, response
from typer.testing import CliRunner

from plannerbench import runner as runner_module
from plannerbench.cli import app

cli = CliRunner()

CASES = """
[[cases]]
id = "color-country"
query = "blue from brazil"
accept = [{ search_by_color = {}, search_by_location = { country = "BR" } }]

[[cases]]
id = "similar"
query = "monarch look-alikes"
accept = [{ search_by_image_similarity = { reference_species = "Danaus plexippus" } }]
"""


@pytest.fixture
def cases_file(tmp_path: Path) -> Path:
    path = tmp_path / "cases.toml"
    path.write_text(CASES, encoding="utf-8")
    return path


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record pacing and backoff waits instead of waiting them out."""
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return recorded


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch, sleeps: list[float]) -> FakeClient:
    client = FakeClient(
        {
            ("good", "blue from brazil"): response(
                ("search_by_color", '{"color_description": "blue"}'),
                ("search_by_location", '{"country": "BR"}'),
            ),
            ("good", "monarch look-alikes"): response(
                ("search_by_image_similarity", '{"reference_species": "Danaus plexippus"}')
            ),
            ("weak", "blue from brazil"): response(
                ("search_by_color", '{"color_description": "blue"}'),
                ("search_by_location", '{"country": "Brazil"}'),
            ),
            ("weak", "monarch look-alikes"): TimeoutError("planner timed out"),
        }
    )
    monkeypatch.setattr(runner_module, "make_client", lambda *args, **kwargs: client)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    return client


def test_run_compares_models_and_writes_report(
    spec_file: Path,
    cases_file: Path,
    fake_client: FakeClient,
    sleeps: list[float],
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    result = cli.invoke(
        app,
        [
            "run",
            "-m",
            "good",
            "-m",
            "weak",
            "--spec",
            str(spec_file),
            "--cases",
            str(cases_file),
            "--repeats",
            "2",
            "--base-url",
            "http://llm.test/v1",
            "--reports-dir",
            str(reports),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2 cases x 2 models x 2 repeats = 8 calls" in result.output
    assert "country" in result.output and "does not match" in result.output
    assert "prompt" in result.output and "completion" in result.output and "total" in result.output
    assert len(fake_client.requests) == 8
    assert ">= 0.1 min at 100 RPM" in result.output
    assert sleeps and all(0 < seconds <= 60 / 100 * 8 for seconds in sleeps)
    request = fake_client.requests[0]
    assert request["messages"][0]["content"] == "You are a search router."
    assert request["tool_choice"] == "auto" and "temperature" not in request

    latest = json.loads((reports / "latest.json").read_text())
    manifest = json.loads((reports / latest["planner"]["manifest"]).read_text())
    summaries = {s["model"]: s for s in manifest["summaries"]}
    assert summaries["good"]["accuracy"] == 1.0
    assert summaries["good"]["consistent_cases"] == 2
    assert summaries["good"]["prompt_tokens"] == 400
    assert summaries["good"]["completion_tokens"] == 40
    assert summaries["good"]["total_tokens"] == 440
    assert summaries["weak"]["accuracy"] == 0.0
    assert summaries["weak"]["api_errors"] == 2
    assert summaries["weak"]["invalid_call_rate"] == 0.5
    assert manifest["requests_per_minute"] == 100
    assert manifest["rate_limit_retries"] == 3
    assert "test-key" not in json.dumps(manifest)

    trials = Path(manifest["outputs"]["trials"]).read_text().splitlines()
    assert len(trials) == 8


def test_run_filters_cases_and_can_skip_writing(
    spec_file: Path,
    cases_file: Path,
    fake_client: FakeClient,
    sleeps: list[float],
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    result = cli.invoke(
        app,
        [
            "run",
            "-m",
            "good",
            "--spec",
            str(spec_file),
            "--cases",
            str(cases_file),
            "--case",
            "similar",
            "-n",
            "1",
            "--base-url",
            "http://llm.test/v1",
            "--reports-dir",
            str(reports),
            "--no-write",
            "--temperature",
            "0",
            "--rpm",
            "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(fake_client.requests) == 1
    assert sleeps == []
    assert "RPM" not in result.output
    assert fake_client.requests[0]["temperature"] == 0
    assert not reports.exists()


def test_missing_spec_explains_how_to_export(tmp_path: Path, fake_client: FakeClient) -> None:
    result = cli.invoke(
        app,
        ["run", "-m", "good", "--spec", str(tmp_path / "nope.json"), "--base-url", "http://x"],
    )
    assert result.exit_code == 2
    assert "export_planner_spec.py" in result.output


def test_missing_api_key_is_reported(spec_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    result = cli.invoke(
        app, ["run", "-m", "good", "--spec", str(spec_file), "--base-url", "http://x"]
    )
    assert result.exit_code == 2
    assert "LLM_API_KEY" in result.output


def test_cases_command_lists_packaged_cases() -> None:
    result = cli.invoke(app, ["cases"])
    assert result.exit_code == 0
    assert "color-country\tblue from brazil" in result.output


def test_run_defaults_to_five_repeats(
    spec_file: Path, cases_file: Path, fake_client: FakeClient
) -> None:
    result = cli.invoke(
        app,
        [
            "run",
            "-m",
            "good",
            "--spec",
            str(spec_file),
            "--cases",
            str(cases_file),
            "--base-url",
            "http://llm.test/v1",
            "--no-write",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2 cases x 1 models x 5 repeats = 10 calls" in result.output
    assert len(fake_client.requests) == 10


def test_concurrency_is_capped_at_the_gateway_limit(
    spec_file: Path, cases_file: Path, fake_client: FakeClient
) -> None:
    result = cli.invoke(
        app,
        ["run", "-m", "good", "--spec", str(spec_file), "--cases", str(cases_file), "-j", "11"],
    )
    assert result.exit_code == 2
    assert not fake_client.requests
