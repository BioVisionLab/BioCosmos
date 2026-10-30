"""The index benchmark's sweep, held-out queries, recall, and selection on a small table."""

import json
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd
import pyarrow as pa
import pytest
from analyses.benchmarks import lance_indexing
from analyses.benchmarks.lance_indexing import (
    BASELINE,
    PRODUCTION_SEARCH,
    BenchmarkConfig,
    SearchSetting,
    SourceSettings,
    accepted_neighbors,
    bootstrap_interval,
    build_parameters,
    copy_for_benchmark,
    open_source,
    recall_at_k,
    recommend,
    run_benchmark,
    search,
    search_settings,
    validate_source,
)

ROWS = 3_000
DIMS = {"unicom_embeddings": 16, "clip_embeddings": 8}


def unit_vectors(rng: np.random.Generator, rows: int, dims: int) -> pa.FixedSizeListArray:
    values = rng.normal(size=(rows, dims)).astype(np.float32)
    values /= np.linalg.norm(values, axis=1, keepdims=True)

    return pa.FixedSizeListArray.from_arrays(pa.array(values.ravel()), dims)


@pytest.fixture
def source(tmp_path: Path) -> SourceSettings:
    rng = np.random.default_rng(0)
    data = pa.table(
        {
            "img_id": [f"img_{i:05d}" for i in range(ROWS)],
            **{column: unit_vectors(rng, ROWS, dims) for column, dims in DIMS.items()},
        }
    )
    database = tmp_path / "source.lance"
    lancedb.connect(str(database)).create_table("images", data=data)

    return SourceSettings(database, "images", tmp_path / "runs")


def small_config(**overrides) -> BenchmarkConfig:
    options = {
        "query_count": 20,
        "repeats": 1,
        "warmup_queries": 2,
        "num_partitions": 8,
        "pq_sub_vectors": 4,
        "hnsw_pq_sub_vectors": 4,
        "nprobes_grid": (1, 8),
        "ef_grid": (None, 40),
        "refine_grid": (None, 10),
        "production": SearchSetting(nprobes=8, refine_factor=10),
        "index_types": ("IVF_PQ",),
        "vector_columns": ("unicom_embeddings",),
        "bootstrap": 200,
    }

    return BenchmarkConfig(**{**options, **overrides})


def test_hnsw_settings_sweep_ef_and_others_do_not():
    config = BenchmarkConfig(nprobes_grid=(5, 20), ef_grid=(None, 40), refine_grid=(None, 10))
    ivf = search_settings("IVF_PQ", 256, config)
    hnsw = search_settings("IVF_HNSW_SQ", 256, config)

    assert {setting.ef for setting in ivf} == {None}
    assert {setting.ef for setting in hnsw} == {None, 40}
    # ef 40 cannot serve the 100 candidates a refine factor of 10 fetches for top 10.
    assert all(s.ef is None or (s.refine_factor or 1) * 10 <= s.ef for s in hnsw)
    assert len(hnsw) == 2 * 2 * 2 - 2
    assert PRODUCTION_SEARCH in ivf and PRODUCTION_SEARCH in hnsw


def test_settings_drop_probes_beyond_the_partitions_but_keep_production():
    config = BenchmarkConfig(
        nprobes_grid=(5, 160), ef_grid=(None,), refine_grid=(None,), production=SearchSetting(40)
    )
    settings = search_settings("IVF_PQ", 100, config)

    assert SearchSetting(160) not in settings
    assert settings == [SearchSetting(5), SearchSetting(40)]


def test_baseline_has_one_setting():
    assert search_settings(BASELINE, 256, BenchmarkConfig()) == [SearchSetting()]


@pytest.mark.parametrize(
    "overrides",
    [
        {"ef_grid": (None, 5)},
        {"nprobes_grid": ()},
        {"refine_grid": (2, 2)},
        {"refine_grid": (0,)},
        {"num_partitions": "many"},
        {"production": SearchSetting(nprobes=0)},
    ],
)
def test_config_rejects_invalid_grids(overrides):
    with pytest.raises(ValueError):
        BenchmarkConfig(**overrides)


def test_auto_build_matches_the_backend_rule():
    config = BenchmarkConfig()

    assert build_parameters(619_787, 768, config) == lance_indexing.BuildParameters(787, 96, 96)
    assert build_parameters(619_787, 512, config).pq_sub_vectors == 64
    # Small tables are sized as if they had the backend's minimum indexed row count.
    assert build_parameters(1_000, 16, config).num_partitions == 70
    assert build_parameters(1_000, 16, small_config()).num_partitions == 8


def test_recall_counts_ties_with_the_kth_neighbor():
    ids = ["a", "b", "c", "d"]
    accepted = accepted_neighbors(ids, [0.1, 0.2, 0.3, 0.3], k=3)

    assert accepted == {"a", "b", "c", "d"}
    assert recall_at_k(["a", "b", "c"], accepted, 3) == 1.0
    assert recall_at_k(["a", "b", "d"], accepted, 3) == 1.0
    assert recall_at_k(["a", "b", "x"], accepted, 3) == pytest.approx(2 / 3)
    assert recall_at_k(list("abcdefghij"[:9]) + ["z"], set("abcdefghij"), 10) == 0.9


def test_accepted_neighbors_needs_k_results():
    with pytest.raises(ValueError):
        accepted_neighbors(["a"], [0.1], k=2)


def test_bootstrap_interval_brackets_the_mean():
    low, high = bootstrap_interval([0.8, 0.9, 1.0, 1.0], resamples=500, seed=1)

    assert low <= 0.925 <= high
    assert bootstrap_interval([1.0] * 5, resamples=50, seed=1) == (1.0, 1.0)


def test_queries_are_held_out_of_the_searched_copy(source, tmp_path):
    config = small_config()
    table = open_source(source)
    total, _ = validate_source(table, config)
    copy, samples = copy_for_benchmark(table, tmp_path / "copy.lance", config, total)
    copied_ids = set(copy.to_arrow().column("img_id").to_pylist())
    query_ids = {sample["img_id"] for sample in samples}

    assert copy.count_rows() == ROWS - config.query_count
    assert len(query_ids) == config.query_count
    assert not copied_ids & query_ids

    for sample in samples:
        result = search(
            copy, sample["unicom_embeddings"], "unicom_embeddings", SearchSetting(), 10, exact=True
        )

        assert sample["img_id"] not in result.column("img_id").to_pylist()


def test_search_projects_to_id_and_distance(source):
    table = open_source(source)
    vector = table.to_arrow().column("unicom_embeddings")[0].as_py()
    result = search(table, vector, "unicom_embeddings", SearchSetting(), 5, exact=True)

    assert result.schema.names == ["img_id", "_distance"]
    assert result.num_rows == 5


def test_recommend_picks_the_fastest_setting_at_the_threshold():
    results = pd.DataFrame(
        [
            ("IVF_PQ", 5, None, 0.90, 1.0),
            ("IVF_PQ", 20, 10, 0.97, 4.0),
            ("IVF_PQ", 40, 10, 0.99, 6.0),
            ("IVF_HNSW_PQ", 5, None, 0.70, 1.0),
            ("IVF_HNSW_PQ", 20, None, 0.80, 2.0),
        ],
        columns=["index", "nprobes", "refine_factor", "recall@10", "avg_ms"],
    ).assign(vector_column="unicom_embeddings", model="UNICOM", ef=None, p95_ms=0.0)
    picks = recommend(results, BenchmarkConfig()).set_index("index")

    assert picks.loc["IVF_PQ", "nprobes"] == 20
    assert bool(picks.loc["IVF_PQ", "meets_threshold"])
    assert not picks.loc["IVF_HNSW_PQ", "meets_threshold"]
    assert picks.loc["IVF_HNSW_PQ", "recall@10"] == 0.80


def test_run_sweeps_every_setting_and_records_the_build(source, tmp_path, monkeypatch):
    monkeypatch.setattr(lance_indexing, "ANALYSES", tmp_path.resolve())
    # HNSW exercises `ef` against LanceDB, which rejects ef below the fetched candidates.
    config = small_config(index_types=("IVF_PQ", "IVF_HNSW_SQ"), ef_grid=(None, 40, 100))
    frame, recommendations, run_dir = run_benchmark(source, config)
    manifest = json.loads((run_dir / "run.json").read_text())
    indexed = frame.loc[frame["index"] == "IVF_PQ"]

    assert manifest["status"] == "complete"
    assert manifest["searched_rows"] == ROWS - config.query_count
    assert manifest["build_parameters"]["unicom_embeddings"]["num_partitions"] == 8
    assert len(manifest["query_img_ids"]) == config.query_count
    assert len(indexed) == len(search_settings("IVF_PQ", 8, config))
    assert (frame["index"] == "IVF_HNSW_SQ").sum() == len(search_settings("IVF_HNSW_SQ", 8, config))
    assert indexed["is_production"].sum() == 1
    assert frame.loc[frame["index"] == BASELINE, "recall@10"].item() == 1.0
    assert (frame["recall_low"] <= frame["recall@10"]).all()
    assert (frame["recall@10"] <= frame["recall_high"]).all()

    probe_all = indexed.loc[(indexed["nprobes"] == 8) & (indexed["refine_factor"] == 10)]

    assert probe_all["recall@10"].item() >= 0.95
    assert set(recommendations["index"]) == {BASELINE, "IVF_PQ", "IVF_HNSW_SQ"}
    assert (run_dir / "query_timings.csv").is_file()


def test_run_refuses_outputs_outside_analyses(source):
    with pytest.raises(ValueError, match="analyses"):
        run_benchmark(source, small_config())
