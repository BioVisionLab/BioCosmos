"""Write one benchmark run under ``reports/planner/<run_id>/``."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from harmonize_core.outputs import write_json_atomically
from harmonize_core.reports import run_directory, update_latest
from pydantic import BaseModel

from plannerbench.scoring import ModelSummary, Trial

REPORT_KIND = "planner"
SCHEMA_VERSION = 1
MANIFEST_NAME = "run.json"
TRIALS_NAME = "trials.jsonl"


class RunManifest(BaseModel):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    package_version: str
    started_at: str
    completed_at: str
    runtime_seconds: float
    spec_path: str
    spec_fingerprint: str
    production_model: str | None
    cases_source: str
    case_ids: list[str]
    models: list[str]
    repeats: int
    concurrency: int
    temperature: float | None
    base_url: str
    summaries: list[ModelSummary]
    outputs: dict[str, str] = {}


def write_run(reports_dir: Path, manifest: RunManifest, trials: list[Trial]) -> Path:
    """Write the trials and manifest, then point ``latest.json`` at the run."""
    output_dir = run_directory(reports_dir, REPORT_KIND, manifest.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    trials_path = output_dir / TRIALS_NAME
    temporary = output_dir / f".{TRIALS_NAME}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        "".join(trial.model_dump_json() + "\n" for trial in trials), encoding="utf-8"
    )
    os.replace(temporary, trials_path)

    manifest_path = output_dir / MANIFEST_NAME
    manifest.outputs = {
        "manifest": str(manifest_path.resolve()),
        "trials": str(trials_path.resolve()),
    }
    write_json_atomically(manifest_path, manifest.model_dump(mode="json"))
    update_latest(
        reports_dir,
        REPORT_KIND,
        run_id=manifest.run_id,
        completed_at=manifest.completed_at,
        manifest=manifest_path,
    )
    return manifest_path
