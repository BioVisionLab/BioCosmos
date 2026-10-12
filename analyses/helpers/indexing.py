"""Index benchmark panel: mean latency against recall@10 for each index and embedding.

Reads the newest completed run through `publication.benchmark_data`, which keeps the
unindexed baseline and leaves out "Flat (brute-force)".
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from analyses.helpers.publication import DEFAULT_PALETTE, benchmark_data

BASELINE = "No Index (baseline)"
MODEL_MARKERS = {"UNICOM": "s", "CLIP": "o"}


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
    """The latest benchmark, with `best_index` marking each embedding's Pareto leaders.

    An index is chosen for one embedding model, so it is only compared with the other
    indexes on the same embeddings.
    """

    benchmark = benchmark_data(root)
    indexed = benchmark.loc[benchmark["index"] != BASELINE]
    leaders = [label for _, group in indexed.groupby("model") for label in pareto_leaders(group)]
    benchmark["best_index"] = benchmark.index.isin(leaders)

    return benchmark


def legend_marker(label, *, color, marker="s", edge="white", width=0.8, size=8) -> Line2D:
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


def index_panel(
    ax, benchmark: pd.DataFrame, legend_fontsize: float = 10, marker_scale: float = 1.0
) -> None:
    """Recall@10 against mean latency; leaders are outlined and joined per embedding.

    `marker_scale` multiplies marker areas, for figures printed smaller.
    """

    indexes = list(dict.fromkeys(benchmark["index"]))
    palette = dict(
        zip(indexes, sns.color_palette(DEFAULT_PALETTE, n_colors=len(indexes)), strict=True)
    )

    for _, rows in benchmark.loc[benchmark["best_index"]].groupby("model"):
        if len(rows) > 1:
            frontier = rows.sort_values("avg_ms")
            ax.plot(
                frontier["avg_ms"],
                frontier["recall@10"],
                color="#333333",
                linewidth=1.25,
                alpha=0.45,
                zorder=1,
            )

    for _, row in benchmark.iterrows():
        best = row["best_index"]
        ax.scatter(
            row["avg_ms"],
            row["recall@10"],
            color=palette[row["index"]],
            marker=MODEL_MARKERS[row["model"]],
            edgecolor="black" if best else "white",
            linewidth=1.6 if best else 0.8,
            s=(150 if best else 75) * marker_scale,
            alpha=1 if best else 0.72,
            zorder=3 if best else 2,
        )

    ax.set(xlabel="Mean latency (ms, log scale)", ylabel="Recall@10", ylim=(0, 1.04))
    ax.set_xscale("log")
    handles = [
        *(legend_marker(index.replace("_", "-"), color=palette[index]) for index in indexes),
        *(
            legend_marker(model, color="#333333", marker=marker)
            for model, marker in MODEL_MARKERS.items()
            if model in set(benchmark["model"])
        ),
        legend_marker("Best index", color="white", marker="o", edge="black", width=1.6, size=10),
    ]
    # Inside the axes, where the low-recall/high-latency corner stays empty, so the
    # legend costs no figure width.
    ax.legend(
        handles=handles,
        title="Index/model",
        loc="lower right",
        frameon=False,
        fontsize=legend_fontsize,
        title_fontsize=legend_fontsize + 1,
    )
    sns.despine(ax=ax)
