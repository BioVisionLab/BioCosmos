"""Planner model benchmark: one plannerbench run, its quality–cost and per-case panels.

The run is read from `reports/latest.json`, or from the manifest named by
`BIOCOSMOS_PLANNER_MANIFEST`. Nothing is written outside `analyses/`.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from analyses.helpers.publication import DEFAULT_PALETTE, project_root


@dataclass(frozen=True)
class PlannerRun:
    manifest: dict
    manifest_path: Path
    trials: pd.DataFrame
    summary: pd.DataFrame
    models: list[str]
    palette: dict
    per_case: pd.DataFrame


def manifest_path(root: Path | None = None) -> Path:
    """The selected planner manifest: the override, else the latest planner run."""
    override = os.getenv("BIOCOSMOS_PLANNER_MANIFEST")
    if override:
        path = Path(override).expanduser().resolve()
    else:
        reports_dir = project_root(root) / "reports"
        latest_path = reports_dir / "latest.json"
        if not latest_path.is_file():
            raise FileNotFoundError(
                "No reports/latest.json found. Run plannerbench or set "
                "BIOCOSMOS_PLANNER_MANIFEST to a planner run.json."
            )
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        planner_latest = latest.get("planner")
        if not planner_latest or not planner_latest.get("manifest"):
            raise ValueError("reports/latest.json has no planner benchmark entry")
        path = (reports_dir / planner_latest["manifest"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Planner manifest not found: {path}")
    return path


def load_planner_run(root: Path | None = None) -> PlannerRun:
    """Load the manifest and its trials, resolving `trials.jsonl` beside the manifest.

    Absolute artifact paths recorded on another machine are ignored.
    """
    path = manifest_path(root)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    trials_path = path.parent / "trials.jsonl"
    if not trials_path.is_file():
        raise FileNotFoundError(f"Planner trials not found beside manifest: {trials_path}")
    trials = pd.read_json(trials_path, lines=True)
    models = manifest.get("models", [])
    if not models or not manifest.get("summaries"):
        raise ValueError("Planner manifest has no models or summaries")
    if trials.empty:
        raise ValueError("Planner trials file is empty")
    palette = dict(
        zip(models, sns.color_palette(DEFAULT_PALETTE, n_colors=len(models)), strict=True)
    )
    summary = pd.DataFrame(manifest["summaries"]).set_index("model").reindex(models)
    for column in ("prompt_tokens", "completion_tokens"):
        if column not in summary:
            summary[column] = 0
    if "total_tokens" not in summary:
        summary["total_tokens"] = summary["prompt_tokens"] + summary["completion_tokens"]
    summary["successful_trials"] = summary["trials"] - summary["api_errors"]
    summary["tokens_per_success"] = summary["total_tokens"] / summary["successful_trials"].replace(
        0, pd.NA
    )
    repeats = manifest["repeats"]
    per_case = pd.DataFrame(
        {
            model: {
                case_id: summary.loc[model, "per_case_correct"][case_id] / repeats
                for case_id in manifest["case_ids"]
            }
            for model in models
        }
    ).T
    return PlannerRun(manifest, path, trials, summary, models, palette, per_case)


def describe(run: PlannerRun) -> str:
    manifest = run.manifest
    return "\n".join(
        (
            f"Run: {manifest.get('run_id', run.manifest_path.parent.name)}",
            f"Production model: {manifest.get('production_model', 'unknown')}",
            f"Prompt fingerprint: {manifest.get('spec_fingerprint', 'unknown')}",
            f"{len(manifest.get('case_ids', []))} cases × {manifest.get('repeats', '?')} "
            f"repeats × {len(run.models)} models = {len(run.trials)} recorded trials",
        )
    )


def unavailable_models(run: PlannerRun) -> list[str]:
    """Models without a successful call: provider failures, not model results."""
    summary = run.summary
    return summary.index[summary["api_errors"] == summary["trials"]].tolist()


def pareto_leaders(frame: pd.DataFrame, cost_column: str) -> list:
    """Rows no other row matches on accuracy and cost while beating it on one."""
    leaders = []
    for model, row in frame.iterrows():
        no_worse = (frame["accuracy"] >= row["accuracy"]) & (frame[cost_column] <= row[cost_column])
        strictly_better = (frame["accuracy"] > row["accuracy"]) | (
            frame[cost_column] < row[cost_column]
        )
        if not (no_worse & strictly_better).any():
            leaders.append(model)
    return leaders


def eligible(run: PlannerRun) -> pd.DataFrame:
    return run.summary.loc[run.summary["successful_trials"] > 0]


def quality_cost_panel(
    ax,
    run: PlannerRun,
    cost_column: str,
    xlabel: str,
    title: str,
    title_loc: str = "center",
    marker_scale: float = 1.0,
) -> None:
    """Accuracy against one cost, with the Pareto leaders outlined and joined.

    `marker_scale` multiplies marker areas, for figures printed smaller.
    """
    panel = eligible(run)[["accuracy", cost_column]].apply(pd.to_numeric, errors="coerce").dropna()
    panel = panel.loc[panel["accuracy"].map(math.isfinite) & panel[cost_column].map(math.isfinite)]
    leaders = pareto_leaders(panel, cost_column)
    frontier = panel.loc[leaders].sort_values(cost_column)
    if len(frontier) > 1:
        ax.plot(
            frontier[cost_column],
            frontier["accuracy"],
            color="#333333",
            linewidth=1.25,
            alpha=0.45,
            zorder=1,
        )
    for model, row in panel.iterrows():
        is_leader = model in leaders
        ax.scatter(
            row[cost_column],
            row["accuracy"],
            color=run.palette[model],
            edgecolor="black" if is_leader else "white",
            linewidth=1.6 if is_leader else 0.8,
            s=(150 if is_leader else 75) * marker_scale,
            alpha=1 if is_leader else 0.72,
            zorder=3 if is_leader else 2,
        )
    if panel.empty:
        ax.text(0.5, 0.5, "No eligible models", transform=ax.transAxes, ha="center")
    ax.set(xlabel=xlabel, ylabel="Accuracy", ylim=(0, 1.03))
    ax.set_title(title, loc=title_loc)
    sns.despine(ax=ax)


def model_legend_handles(run: PlannerRun) -> list[Line2D]:
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=run.palette[model],
            markeredgecolor="white",
            markersize=8,
            label=model,
        )
        for model in run.models
    ]
    handles.append(
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="white",
            markeredgecolor="black",
            markeredgewidth=1.6,
            markersize=10,
            label="Best performance model",
        )
    )
    return handles


def per_case_panel(
    ax,
    run: PlannerRun,
    title: str,
    title_loc: str = "center",
    label_size: float = 12,
    value_size: float = 14,
) -> None:
    """Share of correct repeats per model and benchmark case."""
    sns.heatmap(
        run.per_case,
        annot=True,
        annot_kws={"fontsize": value_size},
        fmt=".0%",
        cmap=sns.light_palette(run.palette[run.models[0]], as_cmap=True),
        vmin=0,
        vmax=1,
        cbar_kws={"label": "Correct repeats"},
        ax=ax,
    )
    ax.set(xlabel="Case", ylabel="Model")
    ax.set_title(title, loc=title_loc)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    ax.tick_params(axis="x", labelsize=label_size)
    ax.tick_params(axis="y", rotation=0, labelsize=label_size)


def trade_off_data(run: PlannerRun) -> pd.DataFrame:
    return eligible(run)[
        ["accuracy", "latency_p50_seconds", "tokens_per_success", "successful_trials"]
    ].reset_index()


def per_case_data(run: PlannerRun) -> pd.DataFrame:
    return (
        run.per_case.rename_axis("model")
        .reset_index()
        .melt(id_vars="model", var_name="case", value_name="accuracy")
    )
