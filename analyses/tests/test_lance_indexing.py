"""Exercise optional indexing experiments against small real Lance tables."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import nbformat
import numpy as np
import pandas as pd
import pytest
from nbclient import NotebookClient

lancedb = pytest.importorskip("lancedb", reason="Install the indexing extra to test benchmarks")
pa = pytest.importorskip("pyarrow")

from analyses.benchmarks.lance_indexing import (  # noqa: E402
    BenchmarkConfig,
    SourceSettings,
    load_source,
    open_source,
    recommend,
    run_benchmark,
    search,
    validate_source,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def lance_source(tmp_path):
    rng = np.random.default_rng(12)
    schema = pa.schema(
        [
            ("img_id", pa.string()),
            ("img_path", pa.string()),
            ("clip_embeddings", pa.list_(pa.float32(), 8)),
            ("unicom_embeddings", pa.list_(pa.float32(), 8)),
        ]
    )
    data = pa.Table.from_pydict(
        {
            "img_id": [f"image-{i}" for i in range(512)],
            "img_path": [f"images/{i}.webp" for i in range(512)],
            "clip_embeddings": rng.normal(size=(512, 8)).astype("float32").tolist(),
            "unicom_embeddings": rng.normal(size=(512, 8)).astype("float32").tolist(),
        },
        schema=schema,
    )
    database = tmp_path / "biocosmos.lance"
    table = lancedb.connect(str(database)).create_table("nymphalidae", data=data)
    table.create_index("img_id", config=lancedb.index.BTree())
    return SourceSettings(database, "nymphalidae", ROOT / "results/indexing-tests" / uuid4().hex)


def small_config(**overrides):
    return replace(
        BenchmarkConfig(
            query_count=8,
            repeats=2,
            warmup_queries=2,
            top_k=5,
            num_partitions=2,
            pq_sub_vectors=2,
            hnsw_pq_sub_vectors=2,
        ),
        **overrides,
    )


def test_all_index_types_and_both_models_leave_source_unchanged(lance_source):
    source = open_source(lance_source)
    version = source.version
    indexes = [(i.name, i.columns) for i in source.list_indices()]
    config = small_config()
    results, recommendations, run = run_benchmark(lance_source, config)
    current = lancedb.connect(str(lance_source.database)).open_table(lance_source.table)
    assert current.version == version
    assert [(i.name, i.columns) for i in current.list_indices()] == indexes
    assert len(results) == 8
    assert set(results["metric"]) == {"cosine"}
    assert (results["build_seconds"] >= 0).all()
    assert results["recall@5"].between(0, 1).all()
    assert set(results.loc[results["index"] == "No Index (baseline)", "recall@5"]) == {1.0}
    assert len(recommendations) == 2
    manifest = json.loads((run / "run.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["source_version"] == version
    assert len(manifest["query_img_ids"]) == config.query_count
    assert manifest["query_img_ids"] != [f"image-{i}" for i in range(config.query_count)]
    observations = pd.read_csv(run / "query_timings.csv")
    assert len(observations) == 8 * config.query_count * config.repeats
    for _, group in observations.groupby(["vector_column", "index"]):
        assert set(group["query_img_id"]) == set(manifest["query_img_ids"])
    assert not list(run.glob("*.png"))


def test_queries_use_cosine_not_l2(tmp_path):
    table = lancedb.connect(str(tmp_path / "cosine.lance")).create_table(
        "images",
        data=pa.Table.from_pydict(
            {
                "img_id": ["a", "b", "c"],
                "clip_embeddings": [[1, 0], [100, 2], [2, 1]],
            },
            schema=pa.schema(
                [("img_id", pa.string()), ("clip_embeddings", pa.list_(pa.float32(), 2))]
            ),
        ),
    )
    result = search(table, [1, 0], "clip_embeddings", small_config(top_k=2), exact=True)
    assert result.column("img_id").to_pylist() == ["a", "b"]


def test_recommendations_do_not_choose_below_threshold_or_mix_columns():
    frame = pd.DataFrame(
        [
            {"vector_column": "clip_embeddings", "index": "IVF_PQ", "avg_ms": 1, "recall@5": 0.5},
            {
                "vector_column": "clip_embeddings",
                "index": "No Index (baseline)",
                "avg_ms": 10,
                "recall@5": 1,
            },
            {"vector_column": "unicom_embeddings", "index": "IVF_PQ", "avg_ms": 3, "recall@5": 0.8},
        ]
    )
    rows = recommend(frame, small_config()).set_index("vector_column")
    assert rows.loc["clip_embeddings", "index"] == "No Index (baseline)"
    assert pd.isna(rows.loc["unicom_embeddings", "index"])


def test_schema_and_query_count_validation(lance_source):
    source = open_source(lance_source)
    with pytest.raises(ValueError, match="divisible"):
        validate_source(source, small_config(pq_sub_vectors=3))
    with pytest.raises(ValueError, match="query_count"):
        validate_source(source, small_config(query_count=513))


def test_duplicate_image_ids_fail_without_modifying_source(lance_source):
    table = lancedb.connect(str(lance_source.database)).open_table(lance_source.table)
    table.add(table.head(1))
    version = table.version
    with pytest.raises(Exception, match="img_id must be unique"):
        run_benchmark(lance_source, small_config(index_types=()))
    manifests = list(lance_source.runs.glob("*/run.json"))
    assert len(manifests) == 1
    assert json.loads(manifests[0].read_text())["status"] == "failed"
    assert (
        lancedb.connect(str(lance_source.database)).open_table(lance_source.table).version
        == version
    )


def test_missing_source_is_not_created(lance_source, tmp_path):
    path = tmp_path / "absent.lance"
    with pytest.raises(FileNotFoundError):
        open_source(replace(lance_source, database=path))
    assert not path.exists()


def test_configuration_does_not_depend_on_duckdb(monkeypatch):
    monkeypatch.setenv("LANCE_DIR", "relative-lance")
    monkeypatch.delenv("DUCK_DIR", raising=False)
    settings = load_source(ROOT.parent)
    assert settings.database == ROOT.parent / "backend/relative-lance/biocosmos.lance"
    assert settings.table == "nymphalidae"


def test_clean_notebook_executes_separately(lance_source, monkeypatch):
    path = ROOT / "benchmarks/image_indexing.ipynb"
    original = path.read_bytes()
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    # Change only the in-memory test copy to suit the small fixture. The delivered
    # notebook retains full-dataset defaults and no saved outputs.
    for cell in notebook.cells:
        if cell.cell_type == "code" and "config = BenchmarkConfig(" in cell.source:
            cell.source = cell.source.replace("query_count=100", "query_count=4")
            cell.source = cell.source.replace("num_partitions=256", "num_partitions=2")
            cell.source = cell.source.replace("pq_sub_vectors=128", "pq_sub_vectors=2")
            cell.source = cell.source.replace("hnsw_pq_sub_vectors=64", "hnsw_pq_sub_vectors=2")
            cell.source = cell.source.replace(
                'index_types=("IVF_PQ", "IVF_HNSW_SQ", "IVF_HNSW_PQ")', "index_types=()"
            )
        if cell.cell_type == "code" and "source_settings = load_source(ROOT)" in cell.source:
            cell.source += (
                "\nfrom dataclasses import replace\n"
                f"source_settings = replace(source_settings, runs=Path({str(lance_source.runs)!r}))"
            )
    monkeypatch.setenv("LANCE_DIR", str(lance_source.database.parent))
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={
            "metadata": {"path": str(ROOT / "benchmarks")},
        },
    ).execute()
    assert path.read_bytes() == original
    assert all(not cell.get("outputs") for cell in nbformat.read(path, as_version=4).cells)
