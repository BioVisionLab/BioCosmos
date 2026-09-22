from __future__ import annotations

import json
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def test_planner_model_performance_notebook_executes(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "planner" / "test-run"
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "run.json"
    quality_model = "quality-leader-with-a-very-long-model-name"
    fast_model = "fast-efficient-model-with-a-very-long-model-name"
    dominated_model = "dominated-model-with-a-very-long-model-name"
    unavailable_model = "unavailable-provider-model-with-a-very-long-model-name"
    manifest = {
        "run_id": "test-run",
        "production_model": "gemma-4-31b-it",
        "spec_fingerprint": "f" * 64,
        "case_ids": ["color", "location"],
        "models": [quality_model, fast_model, dominated_model, unavailable_model],
        "repeats": 2,
        "summaries": [
            {
                "model": quality_model,
                "trials": 4,
                "api_errors": 0,
                "accuracy": 1.0,
                "consistent_cases": 2,
                "case_count": 2,
                "no_tool_rate": 0.0,
                "invalid_call_rate": 0.0,
                "latency_p50_seconds": 0.5,
                "latency_p95_seconds": 0.7,
                "prompt_tokens": 400,
                "completion_tokens": 40,
                "total_tokens": 440,
                "per_case_correct": {"color": 2, "location": 2},
            },
            {
                "model": fast_model,
                "trials": 4,
                "api_errors": 0,
                "accuracy": 0.75,
                "consistent_cases": 1,
                "case_count": 2,
                "no_tool_rate": 0.0,
                "invalid_call_rate": 0.1,
                "latency_p50_seconds": 0.2,
                "latency_p95_seconds": 0.3,
                "prompt_tokens": 280,
                "completion_tokens": 40,
                "total_tokens": 320,
                "per_case_correct": {"color": 2, "location": 1},
            },
            {
                "model": dominated_model,
                "trials": 4,
                "api_errors": 0,
                "accuracy": 0.5,
                "consistent_cases": 1,
                "case_count": 2,
                "no_tool_rate": 0.25,
                "invalid_call_rate": 0.1,
                "latency_p50_seconds": 0.6,
                "latency_p95_seconds": 0.8,
                "prompt_tokens": 360,
                "completion_tokens": 40,
                "total_tokens": 400,
                "per_case_correct": {"color": 2, "location": 0},
            },
            {
                "model": unavailable_model,
                "trials": 4,
                "api_errors": 4,
                "accuracy": 0.0,
                "consistent_cases": 0,
                "case_count": 2,
                "no_tool_rate": 0.0,
                "invalid_call_rate": 0.0,
                "latency_p50_seconds": None,
                "latency_p95_seconds": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "per_case_correct": {"color": 0, "location": 0},
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    trials = []
    latency_by_model = {quality_model: 0.5, fast_model: 0.2, dominated_model: 0.6}
    tokens_by_model = {quality_model: 110, fast_model: 80, dominated_model: 100}
    for model in manifest["models"]:
        for case_id in manifest["case_ids"]:
            for repeat in (1, 2):
                is_error = model == unavailable_model
                is_correct = (
                    model == quality_model
                    or (model == fast_model and not (case_id == "location" and repeat == 2))
                    or (model == dominated_model and case_id == "color")
                )
                total_tokens = None if is_error else tokens_by_model[model]
                trials.append(
                    {
                        "model": model,
                        "case_id": case_id,
                        "repeat": repeat,
                        "status": "error" if is_error else "ok",
                        "latency_seconds": (
                            None if is_error else latency_by_model[model] + 0.01 * repeat
                        ),
                        "prompt_tokens": None if is_error else total_tokens - 10,
                        "completion_tokens": None if is_error else 10,
                        "total_tokens": total_tokens,
                        "correct": not is_error and is_correct,
                    }
                )
    (run_dir / "trials.jsonl").write_text(
        "".join(json.dumps(trial) + "\n" for trial in trials), encoding="utf-8"
    )

    path = ROOT / "benchmarks/planner_model_performance.ipynb"
    original = path.read_bytes()
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    monkeypatch.setenv("BIOCOSMOS_PLANNER_MANIFEST", str(manifest_path))

    executed = NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT / "benchmarks")}},
    ).execute()

    assert path.read_bytes() == original
    assert all(not cell.get("outputs") for cell in nbformat.read(path, as_version=4).cells)
    scatter_cell = next(cell for cell in executed.cells if cell.get("id") == "trade-off-scatter")
    assert any(
        output.get("output_type") == "display_data" and "image/png" in output.get("data", {})
        for output in scatter_cell["outputs"]
    )
