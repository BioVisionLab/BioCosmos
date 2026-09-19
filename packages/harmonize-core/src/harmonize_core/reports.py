"""Shared layout and pointer file for the repository ``reports/`` directory."""

from __future__ import annotations

import json
from pathlib import Path

from harmonize_core.errors import OutputError
from harmonize_core.outputs import write_json_atomically

DEFAULT_REPORTS_DIR = Path("reports")
LATEST_NAME = "latest.json"
SCHEMA_VERSION = 1


def run_directory(reports_dir: Path, kind: str, run_id: str) -> Path:
    """Return ``<reports_dir>/<kind>/<run_id>``, the output dir for one run."""
    return reports_dir / kind / run_id


def update_latest(
    reports_dir: Path,
    kind: str,
    *,
    run_id: str,
    completed_at: str,
    manifest: Path,
) -> Path:
    """Point ``latest.json`` at this run, leaving the other tool's entry intact."""
    destination = reports_dir / LATEST_NAME
    payload: dict[str, object] = {"schema_version": SCHEMA_VERSION}
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise OutputError(f"Cannot parse existing pointer file: {destination}") from exc
        if isinstance(existing, dict):
            payload.update(existing)
            payload["schema_version"] = SCHEMA_VERSION
    try:
        relative: str = str(manifest.resolve().relative_to(reports_dir.resolve()))
    except ValueError:
        relative = str(manifest.resolve())
    payload[kind] = {
        "run_id": run_id,
        "completed_at": completed_at,
        "manifest": relative,
    }
    return write_json_atomically(destination, payload)
