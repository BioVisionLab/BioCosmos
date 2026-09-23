"""Command-line interface for plannerbench."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from harmonize_core.errors import ConfigurationError, HarmonizeError
from harmonize_core.reports import DEFAULT_REPORTS_DIR

from plannerbench import __version__, runner
from plannerbench.cases import Case, check_cases_against_spec, load_cases
from plannerbench.reports import RunManifest, write_run
from plannerbench.scoring import ModelSummary, Trial, summarize
from plannerbench.spec import DEFAULT_SPEC_PATH, load_spec

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

# The NaviGator gateway rejects more parallel requests than this.
MAX_CONCURRENCY = 10


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"Error: {exc}", err=True)
    return typer.Exit(code=2)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _select_cases(cases: list[Case], wanted: list[str] | None) -> list[Case]:
    if not wanted:
        return cases
    known = {case.id for case in cases}
    unknown = [case_id for case_id in wanted if case_id not in known]
    if unknown:
        raise ConfigurationError(f"Unknown case ids: {', '.join(unknown)}")
    return [case for case in cases if case.id in set(wanted)]


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}s"


def _echo_summary(summaries: list[ModelSummary], cases: list[Case], repeats: int) -> None:
    width = max(len(summary.model) for summary in summaries)
    typer.echo("")
    typer.echo(
        f"{'model'.ljust(width)}  accuracy   consistent  no-tool  invalid  errors"
        "  p50     p95     max     prompt  completion   total"
    )
    for s in summaries:
        typer.echo(
            f"{s.model.ljust(width)}  {s.accuracy:6.1%}"
            f"   {s.consistent_cases:>3}/{s.case_count:<3}"
            f"    {s.no_tool_rate:5.1%}   {s.invalid_call_rate:5.1%}"
            f"   {s.api_errors:>4}"
            f"  {_seconds(s.latency_p50_seconds):>6}  {_seconds(s.latency_p95_seconds):>6}"
            f"  {_seconds(s.latency_max_seconds):>6}"
            f"  {s.prompt_tokens:>9,}  {s.completion_tokens:>10,}  {s.total_tokens:>6,}"
        )

    case_width = max(len(case.id) for case in cases)
    typer.echo("")
    typer.echo(
        f"{'case'.ljust(case_width)}  " + "  ".join(s.model[:12].ljust(12) for s in summaries)
    )
    for case in cases:
        cells = "  ".join(f"{s.per_case_correct[case.id]}/{repeats}".ljust(12) for s in summaries)
        typer.echo(f"{case.id.ljust(case_width)}  {cells}")


def _echo_misses(trials: list[Trial], cases: list[Case]) -> None:
    queries = {case.id: case.query for case in cases}
    misses = [trial for trial in trials if not trial.correct]
    if not misses:
        return
    typer.echo("\nMisses:")
    for trial in misses:
        if trial.status == "error":
            detail = f"ERROR {trial.error}"
        else:
            invalid = [f"{call.name}: {call.error}" for call in trial.calls if not call.valid]
            detail = trial.signature or "{}"
            if invalid:
                detail += f"  invalid={invalid}"
            if not trial.calls and trial.content:
                detail += f"  text={trial.content[:80]!r}"
        typer.echo(
            f"  [{trial.model}] {trial.case_id} #{trial.repeat} "
            f"({queries[trial.case_id]!r}): {detail}"
        )


@app.command("cases")
def cases_command(
    cases_file: Annotated[Path | None, typer.Option("--cases")] = None,
) -> None:
    """List the benchmark cases and the plans each accepts."""
    try:
        for case in load_cases(cases_file):
            plans = " | ".join(" + ".join(sorted(plan)) or "(no tool)" for plan in case.accept)
            typer.echo(f"{case.id}\t{case.query}\t{plans}")
    except HarmonizeError as exc:
        raise _fail(exc) from exc


@app.command("run")
def run_command(
    models: Annotated[
        list[str], typer.Option("--model", "-m", help="Model id; repeat to compare models.")
    ],
    spec_path: Annotated[
        Path, typer.Option("--spec", help="Planner spec exported by the backend.")
    ] = DEFAULT_SPEC_PATH,
    cases_file: Annotated[
        Path | None, typer.Option("--cases", help="Case TOML; defaults to the packaged set.")
    ] = None,
    case_ids: Annotated[
        list[str] | None, typer.Option("--case", help="Run only this case id; repeatable.")
    ] = None,
    repeats: Annotated[int, typer.Option("--repeats", "-n", min=1)] = 5,
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-j",
            min=1,
            max=MAX_CONCURRENCY,
            help="Requests in flight; NaviGator allows 10.",
        ),
    ] = 4,
    rpm: Annotated[
        float,
        typer.Option(
            "--rpm",
            min=0,
            help="Request budget per minute across all concurrent calls; 0 disables pacing. "
            "NaviGator allows 120.",
        ),
    ] = runner.DEFAULT_REQUESTS_PER_MINUTE,
    rate_limit_retries: Annotated[
        int,
        typer.Option("--rate-limit-retries", min=0, help="Retries for each HTTP 429."),
    ] = runner.DEFAULT_RATE_LIMIT_RETRIES,
    temperature: Annotated[
        float | None,
        typer.Option(help="Override the provider default the backend relies on."),
    ] = None,
    base_url: Annotated[
        str | None, typer.Option("--base-url", envvar="LLM_API_URL", show_envvar=True)
    ] = None,
    api_key_env: Annotated[
        str, typer.Option("--api-key-env", help="Environment variable holding the API key.")
    ] = "LLM_API_KEY",
    max_retries: Annotated[int, typer.Option("--max-retries", min=0)] = 0,
    reports_dir: Annotated[Path, typer.Option("--reports-dir")] = DEFAULT_REPORTS_DIR,
    write: Annotated[
        bool, typer.Option("--write/--no-write", help="Save the run under reports/planner/.")
    ] = True,
    show_misses: Annotated[bool, typer.Option("--misses/--no-misses")] = True,
) -> None:
    """Replay the production planner prompt against one or more models."""
    try:
        models = list(dict.fromkeys(models))
        spec = load_spec(spec_path)
        all_cases = load_cases(cases_file)
        cases = _select_cases(all_cases, case_ids)
        check_cases_against_spec(cases, spec)
        if not base_url:
            raise ConfigurationError("Set --base-url or LLM_API_URL.")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ConfigurationError(f"Environment variable {api_key_env} is not set.")
    except HarmonizeError as exc:
        raise _fail(exc) from exc

    total = len(cases) * len(models) * repeats
    pacing = f", >= {total / rpm:.1f} min at {rpm:g} RPM" if rpm else ""
    typer.echo(
        f"Planner spec {spec.fingerprint[:12]} (production model: {spec.production_model}); "
        f"{len(cases)} cases x {len(models)} models x {repeats} repeats = {total} calls"
        f"{pacing}"
    )

    done = 0

    def progress(trial: Trial) -> None:
        nonlocal done
        done += 1
        mark = "ok" if trial.correct else ("ERR" if trial.status == "error" else "miss")
        typer.echo(f"  [{done}/{total}] {trial.model} {trial.case_id} #{trial.repeat}: {mark}")

    started_at, started = _now(), time.perf_counter()
    client = runner.make_client(base_url, api_key, max_retries=max_retries)
    trials = asyncio.run(
        runner.run_benchmark(
            client,
            spec,
            cases,
            models,
            repeats=repeats,
            concurrency=concurrency,
            temperature=temperature,
            requests_per_minute=rpm or None,
            rate_limit_retries=rate_limit_retries,
            on_trial=progress,
        )
    )
    runtime = round(time.perf_counter() - started, 3)
    summaries = summarize(trials, models, cases)

    if show_misses:
        _echo_misses(trials, cases)
    _echo_summary(summaries, cases, repeats)
    retried = sum(trial.rate_limit_retries for trial in trials)
    if retried:
        typer.echo(f"\nRate-limited: {retried} retries (lower --rpm if this keeps happening)")

    if write:
        manifest = RunManifest(
            run_id=str(uuid.uuid4()),
            package_version=__version__,
            started_at=started_at,
            completed_at=_now(),
            runtime_seconds=runtime,
            spec_path=str(spec_path.resolve()),
            spec_fingerprint=spec.fingerprint,
            production_model=spec.production_model,
            cases_source=str(cases_file.resolve()) if cases_file else "packaged",
            case_ids=[case.id for case in cases],
            models=models,
            repeats=repeats,
            concurrency=concurrency,
            requests_per_minute=rpm or None,
            rate_limit_retries=rate_limit_retries,
            temperature=temperature,
            base_url=base_url,
            summaries=summaries,
        )
        try:
            manifest_path = write_run(reports_dir, manifest, trials)
        except HarmonizeError as exc:
            raise _fail(exc) from exc
        typer.echo(f"\nWrote {manifest_path}")


if __name__ == "__main__":  # pragma: no cover
    app()
