"""Index benchmark panels: recall@10 against mean latency, one panel per embedding.

Reads the newest completed run through `publication.benchmark_data`, which keeps the
unindexed baseline and leaves out "Flat (brute-force)".
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator

from analyses.helpers.publication import DEFAULT_PALETTE, benchmark_data

BASELINE = "No Index (baseline)"
MODEL_ORDER = ("UNICOM", "CLIP")
SETTING_COLUMNS = ("nprobes", "ef", "refine_factor")
# Labeled recall ticks on the logit axis, which spreads out the high-recall end where the
# indexes differ; the top tick, perfect recall, is added at the axis ceiling.
RECALL_TICKS = (0.7, 0.9, 0.95, 0.99, 0.999)


def pareto_leaders(frame: pd.DataFrame) -> list:
    """Rows no other row matches on recall and latency while beating it on one."""

    leaders = []

    for label, row in frame.iterrows():
        no_worse = (frame["recall@10"] >= row["recall@10"]) & (frame["avg_ms"] <= row["avg_ms"])
        strictly_better = (frame["recall@10"] > row["recall@10"]) | (
            frame["avg_ms"] < row["avg_ms"]
        )

        if not (no_worse & strictly_better).any():
            leaders.append(label)

    return leaders


def index_benchmark(root: Path | None = None) -> pd.DataFrame:
    """The latest benchmark, with each index's frontier and each embedding's leaders.

    `frontier` marks the Pareto-optimal search settings of one index on one embedding,
    the curve that index can reach. `best_index` marks the Pareto leaders across every
    index and setting of one embedding: an index is chosen for one embedding model, so it
    is only compared with the other indexes on the same embeddings. Runs from before the
    search-setting sweep have one setting per index and load as single points.
    """

    benchmark = benchmark_data(root)

    for column in SETTING_COLUMNS:
        if column not in benchmark:
            benchmark[column] = pd.NA

    if "is_production" not in benchmark:
        benchmark["is_production"] = False

    benchmark["is_production"] = benchmark["is_production"].fillna(False).astype(bool)
    indexed = benchmark.loc[benchmark["index"] != BASELINE]
    frontier = [
        label for _, group in indexed.groupby(["model", "index"]) for label in pareto_leaders(group)
    ]
    leaders = [label for _, group in indexed.groupby("model") for label in pareto_leaders(group)]
    benchmark["frontier"] = benchmark.index.isin(frontier)
    benchmark["best_index"] = benchmark.index.isin(leaders)

    return benchmark


def legend_marker(label, *, color, marker="o", edge="white", width=0.8, size=8) -> Line2D:
    return Line2D(
        [0],
        [0],
        marker=marker,
        color="none",
        markerfacecolor=color,
        markeredgecolor=edge,
        markeredgewidth=width,
        markersize=size,
        label=label,
    )


def models(benchmark: pd.DataFrame) -> list[str]:
    """Embedding models in panel order: the known ones first, then any others."""

    present = list(dict.fromkeys(benchmark["model"]))

    return [model for model in MODEL_ORDER if model in present] + [
        model for model in present if model not in MODEL_ORDER
    ]


def index_colors(benchmark: pd.DataFrame) -> dict:
    """One color per index, in run order, the same in every panel."""

    indexes = [index for index in dict.fromkeys(benchmark["index"]) if index != BASELINE]

    return dict(
        zip(indexes, sns.color_palette(DEFAULT_PALETTE, n_colors=len(indexes)), strict=True)
    )


def recall_floor(benchmark: pd.DataFrame, step: float = 0.05) -> float:
    """The lowest recall any panel draws, rounded down to `step`, so panels share an axis."""

    drawn = benchmark.loc[benchmark["frontier"] | benchmark["is_production"], "recall@10"]
    threshold = benchmark.attrs.get("recall_threshold") or 1.0
    lowest = min(drawn.min(), threshold) if not drawn.empty else threshold

    return max(0.0, math.floor(round(lowest / step, 6)) * step - step / 2)


def recall_ceiling(benchmark: pd.DataFrame) -> float:
    """Where perfect recall is drawn: a logit axis cannot reach 1.

    Half a hit short of every query being exact, below any recall the run can measure
    short of 1 (one miss in `query_count` × 10 results).
    """

    queries = benchmark["query_count"].max() if "query_count" in benchmark else 100

    return 1 - 0.5 / (queries * 10)


def baseline_note(benchmark: pd.DataFrame, model: str) -> str | None:
    rows = benchmark.loc[(benchmark["model"] == model) & (benchmark["index"] == BASELINE)]

    if rows.empty:
        return None

    row = rows.iloc[0]

    return f"Exact search:\n{row['avg_ms']:,.0f} ms, recall {row['recall@10']:.2f}"


def index_panel(
    ax,
    benchmark: pd.DataFrame,
    model: str,
    *,
    floor: float | None = None,
    marker_scale: float = 1.0,
    note_fontsize: float | None = None,
) -> None:
    """Recall@10 against mean latency for one embedding: each index's frontier.

    Only the Pareto-optimal search settings of each index are drawn, joined in latency
    order; the backend's search setting is a black-edged diamond even when it is not on
    the frontier. Recall is on a logit axis, which spreads out the settings near perfect
    recall instead of stacking them; perfect recall is drawn at `recall_ceiling`. The
    exact baseline is too slow to share the axis, so it is a note. The dotted line is the
    recall threshold. `marker_scale` multiplies marker areas, for figures printed smaller.
    """

    colors = index_colors(benchmark)
    ceiling = recall_ceiling(benchmark)
    rows = benchmark.loc[(benchmark["model"] == model) & (benchmark["index"] != BASELINE)]
    threshold = benchmark.attrs.get("recall_threshold")

    if threshold is not None:
        ax.axhline(threshold, color="#777777", linestyle=":", linewidth=1, zorder=0)

    for index, group in rows.groupby("index", sort=False):
        curve = group.loc[group["frontier"]].sort_values("avg_ms")
        ax.plot(
            curve["avg_ms"],
            curve["recall@10"].clip(upper=ceiling),
            color=colors[index],
            marker="o",
            markersize=5 * math.sqrt(marker_scale),
            markeredgecolor="white",
            markeredgewidth=0.6,
            linewidth=1.6,
            zorder=2,
        )
        production = group.loc[group["is_production"]]

        if not production.empty:
            ax.scatter(
                production["avg_ms"],
                production["recall@10"].clip(upper=ceiling),
                color=colors[index],
                marker="D",
                edgecolor="black",
                linewidth=1.1,
                s=45 * marker_scale,
                zorder=4,
            )

    floor = floor if floor is not None else recall_floor(benchmark)
    ticks = [tick for tick in RECALL_TICKS if floor < tick < ceiling]
    ax.set(xlabel="Mean latency (ms)", ylabel="Recall@10 (logit scale)", title=model)
    ax.set_yscale("logit")
    # Headroom above the perfect-recall points, half their distance from 1.
    ax.set_ylim(floor, 1 - (1 - ceiling) / 2)
    ax.set_yticks([*ticks, ceiling], labels=[f"{tick:g}" for tick in ticks] + ["1"])
    ax.yaxis.set_minor_locator(NullLocator())
    ax.margins(x=0.06)
    note = baseline_note(benchmark, model)

    if note is not None:
        # Inside the axes; kept out of the layout so a long note never shrinks the panel.
        ax.text(
            0.98,
            0.03,
            note,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=note_fontsize or "small",
            color="#555555",
        ).set_in_layout(False)

    sns.despine(ax=ax)


def index_legend_handles(benchmark: pd.DataFrame) -> list:
    handles = [
        Line2D(
            [0],
            [0],
            color=color,
            marker="o",
            markeredgecolor="white",
            linewidth=1.6,
            label=index.replace("_", "-"),
        )
        for index, color in index_colors(benchmark).items()
    ]

    if benchmark["is_production"].any():
        handles.append(
            legend_marker("Site's setting", color="white", marker="D", edge="black", width=1.1)
        )

    threshold = benchmark.attrs.get("recall_threshold")

    if threshold is not None:
        handles.append(
            Line2D([0], [0], color="#777777", linestyle=":", label=f"Recall {threshold:g}")
        )

    return handles


def index_panels(
    axes,
    benchmark: pd.DataFrame,
    *,
    legend_fontsize: float = 10,
    marker_scale: float = 1.0,
    note_fontsize: float | None = None,
    legend: bool = True,
) -> None:
    """One `index_panel` per embedding on a shared recall axis, the legend in the first.

    Pass `legend=False` to place `index_legend_handles` elsewhere.
    """

    floor = recall_floor(benchmark)
    panel_models = models(benchmark)

    if len(axes) < len(panel_models):
        raise ValueError(f"Need {len(panel_models)} axes, one per embedding model")

    for position, (ax, model) in enumerate(zip(axes, panel_models, strict=False)):
        index_panel(
            ax,
            benchmark,
            model,
            floor=floor,
            marker_scale=marker_scale,
            note_fontsize=note_fontsize,
        )

        if position:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)

    if not legend:
        return

    # Above the baseline note, in the lower right of the first panel, which is empty: on
    # UNICOM every index passes 0.99 recall before the slower settings at the right.
    axes[0].legend(
        handles=index_legend_handles(benchmark),
        title="Index",
        loc="lower right",
        bbox_to_anchor=(1, 0.16),
        # Opaque, so the threshold line does not run through the entries.
        frameon=True,
        framealpha=1,
        edgecolor="none",
        fontsize=legend_fontsize,
        title_fontsize=legend_fontsize + 1,
    )
