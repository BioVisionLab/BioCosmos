"""The index panel's loader for swept and legacy benchmark runs."""

import json
from pathlib import Path

import pandas as pd
from analyses.helpers.indexing import (
    BASELINE,
    index_benchmark,
    index_panels,
    recall_floor,
)
from matplotlib.figure import Figure


def write_run(root: Path, rows: list[dict]) -> None:
    (root / "backend/app/configs").mkdir(parents=True)
    (root / "backend/app/configs/config.yaml").write_text("{}\n")
    run = root / "analyses/results/indexing/20260101T000000Z_abcdef12"
    run.mkdir(parents=True)
    manifest = {"status": "complete", "config": {"top_k": 10, "recall_threshold": 0.95}}
    (run / "run.json").write_text(json.dumps(manifest))
    pd.DataFrame(rows).to_csv(run / "indexing_benchmark.csv", index=False)


def row(index: str, recall: float, ms: float, model: str = "UNICOM", **settings) -> dict:
    return {"index": index, "model": model, "avg_ms": ms, "recall@10": recall, **settings}


def test_swept_run_marks_each_index_frontier_and_production(tmp_path):
    write_run(
        tmp_path,
        [
            row(BASELINE, 1.0, 600.0, is_production=False),
            row("IVF_PQ", 0.80, 2.0, nprobes=5, ef=None, refine_factor=None, is_production=False),
            row("IVF_PQ", 0.75, 3.0, nprobes=5, ef=None, refine_factor=2, is_production=False),
            row("IVF_PQ", 0.99, 9.0, nprobes=20, ef=None, refine_factor=10, is_production=True),
            row("IVF_HNSW_SQ", 0.97, 3.0, nprobes=20, ef=40, refine_factor=None),
            row(BASELINE, 1.0, 380.0, "CLIP", is_production=False),
            row("IVF_PQ", 0.66, 2.0, "CLIP", nprobes=5, refine_factor=None, is_production=False),
            row("IVF_PQ", 0.98, 4.0, "CLIP", nprobes=20, refine_factor=10, is_production=True),
        ],
    )
    benchmark = index_benchmark(tmp_path)
    pq = benchmark.loc[(benchmark["index"] == "IVF_PQ") & (benchmark["model"] == "UNICOM")]

    assert pq["frontier"].tolist() == [True, False, True]
    assert benchmark["is_production"].sum() == 2
    assert benchmark.attrs["recall_threshold"] == 0.95
    assert benchmark.loc[benchmark["index"] == "IVF_HNSW_SQ", "best_index"].item()

    fig = Figure()
    unicom, clip = fig.subplots(1, 2)
    index_panels([unicom, clip], benchmark)
    pq_curve = next(
        line
        for line in unicom.get_lines()
        if line.get_marker() == "o" and len(line.get_xdata()) == 2
    )

    # Frontier only: the dominated IVF-PQ setting (0.75 at 3 ms) is not drawn.
    assert list(pq_curve.get_xdata()) == [2.0, 9.0]
    assert [ax.get_title() for ax in (unicom, clip)] == ["UNICOM", "CLIP"]
    # One shared recall axis, zoomed to the lowest frontier point.
    assert unicom.get_ylim() == clip.get_ylim()
    assert recall_floor(benchmark) == clip.get_ylim()[0] < 0.66 < 0.75
    assert clip.texts[0].get_text() == "Exact search:\n380 ms, recall 1.00"
    assert unicom.get_legend() is not None and clip.get_legend() is None


def test_legacy_run_without_settings_loads_as_single_points(tmp_path):
    write_run(
        tmp_path,
        [row(BASELINE, 1.0, 600.0), row("IVF_PQ", 0.81, 5.7), row("IVF_HNSW_SQ", 0.98, 3.0)],
    )
    benchmark = index_benchmark(tmp_path)

    assert {"nprobes", "ef", "refine_factor"} <= set(benchmark)
    assert not benchmark["is_production"].any()
    assert benchmark.loc[benchmark["index"] != BASELINE, "frontier"].all()

    fig = Figure()
    index_panels(fig.subplots(1, 2), benchmark)
