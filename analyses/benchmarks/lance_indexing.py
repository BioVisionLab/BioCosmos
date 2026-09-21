"""Benchmark cosine vector indexes on an isolated copy of the backend Lance table."""

from __future__ import annotations

import json
import os
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import lancedb
import numpy as np
import pandas as pd
import pyarrow as pa
import yaml
from dotenv import dotenv_values
from lancedb.index import HnswPq, HnswSq, IvfPq

VECTOR_COLUMNS = ("unicom_embeddings", "clip_embeddings")
INDEX_TYPES = ("IVF_PQ", "IVF_HNSW_SQ", "IVF_HNSW_PQ")


@dataclass(frozen=True)
class SourceSettings:
    database: Path
    table: str
    runs: Path


@dataclass(frozen=True)
class BenchmarkConfig:
    query_count: int = 100
    repeats: int = 3
    warmup_queries: int = 10
    top_k: int = 10
    seed: int = 42
    num_partitions: int = 256
    pq_sub_vectors: int = 128
    hnsw_pq_sub_vectors: int = 64
    nprobes: int | None = None
    refine_factor: int | None = None
    index_types: tuple[str, ...] = INDEX_TYPES
    vector_columns: tuple[str, ...] = VECTOR_COLUMNS
    recall_threshold: float = 0.95

    def __post_init__(self):
        for name in (
            "query_count",
            "repeats",
            "top_k",
            "num_partitions",
            "pq_sub_vectors",
            "hnsw_pq_sub_vectors",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.warmup_queries < 0 or self.seed < 0:
            raise ValueError("warmup_queries and seed must be nonnegative")
        if not 0 <= self.recall_threshold <= 1:
            raise ValueError("recall_threshold must lie between zero and one")
        for name in ("nprobes", "refine_factor"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"{name} must be positive or None")
        if self.nprobes is not None and self.nprobes > self.num_partitions:
            raise ValueError("nprobes cannot exceed num_partitions")
        if not self.vector_columns or len(set(self.vector_columns)) != len(self.vector_columns):
            raise ValueError("Select at least one distinct vector column")
        if not set(self.vector_columns) <= set(VECTOR_COLUMNS):
            raise ValueError(f"Select backend embedding columns from {VECTOR_COLUMNS}")
        if len(set(self.index_types)) != len(self.index_types) or not set(self.index_types) <= set(
            INDEX_TYPES
        ):
            raise ValueError(f"Select distinct index types from {INDEX_TYPES}")


def load_source(root: Path) -> SourceSettings:
    """Read configuration without importing backend or publication code."""
    root = root.resolve()
    backend = root / "backend"
    env = {**dotenv_values(backend / ".env"), **os.environ}
    with (backend / "app/configs/config.yaml").open() as handle:
        config = yaml.safe_load(handle)
    directory = env.get("LANCE_DIR")
    if not directory:
        raise ValueError("Set LANCE_DIR in backend/.env or the kernel environment")
    path = Path(directory).expanduser()
    if not path.is_absolute():
        path = backend / path
    return SourceSettings(
        (path / config["db"]["lance"]["file"]).resolve(),
        config["images"]["table"],
        root / "analyses/results/indexing",
    )


def open_source(settings: SourceSettings):
    """Open an existing source at a fixed version; never create or index it."""
    if not settings.database.is_dir():
        raise FileNotFoundError(f"Backend Lance database not found: {settings.database}")
    table = lancedb.connect(str(settings.database)).open_table(settings.table)
    table.checkout(table.version)
    return table


def validate_source(table, config: BenchmarkConfig) -> tuple[int, dict[str, int]]:
    total = table.count_rows()
    if total <= config.top_k:
        raise ValueError("The source needs more rows than top_k")
    if config.query_count > total:
        raise ValueError("query_count cannot exceed the source row count")
    if "img_id" not in table.schema.names:
        raise ValueError("Source table requires stable img_id values")
    dimensions = {}
    for column in config.vector_columns:
        if column not in table.schema.names:
            raise ValueError(f"Missing backend embedding column: {column}")
        field = table.schema.field(column)
        if not pa.types.is_fixed_size_list(field.type):
            raise ValueError(f"{column} must contain fixed-size embedding vectors")
        dimensions[column] = field.type.list_size
        for index_type, subvectors in (
            ("IVF_PQ", config.pq_sub_vectors),
            ("IVF_HNSW_PQ", config.hnsw_pq_sub_vectors),
        ):
            if index_type in config.index_types and dimensions[column] % subvectors:
                raise ValueError(
                    f"{column} dimension must be divisible by {subvectors} for {index_type}"
                )
    if config.index_types and total < max(256, config.num_partitions):
        raise ValueError("ANN training needs at least 256 rows and at least num_partitions rows")
    return total, dimensions


def copy_for_benchmark(source, destination: Path, config: BenchmarkConfig, total: int):
    """Stream the pinned source to a fresh table and collect seeded query rows."""
    positions = set(
        np.random.default_rng(config.seed).choice(total, config.query_count, replace=False).tolist()
    )
    samples = []
    seen_ids = set()
    reader = source.search().limit(None).to_batches(batch_size=1024)

    def checked_batches():
        offset = 0
        for batch in reader:
            ids = batch.column("img_id").to_pylist()
            if any(not isinstance(value, str) or not value.strip() for value in ids):
                raise ValueError("img_id must contain nonblank strings")
            if len(set(ids)) != len(ids) or seen_ids.intersection(ids):
                raise ValueError("img_id must be unique for recall calculations")
            seen_ids.update(ids)
            for column in config.vector_columns:
                values = np.asarray(batch.column(column).to_pylist(), dtype=np.float32)
                if (
                    values.ndim != 2
                    or not np.isfinite(values).all()
                    or np.any(np.linalg.norm(values, axis=1) == 0)
                ):
                    raise ValueError(f"{column} contains missing, nonfinite, or zero-norm vectors")
            for local_position in range(len(batch)):
                if offset + local_position in positions:
                    samples.append(batch.slice(local_position, 1).to_pylist()[0])
            offset += len(batch)
            yield batch
        if offset != total:
            raise ValueError("Copied row count differs from the pinned source count")

    batches = pa.RecordBatchReader.from_batches(reader.schema, checked_batches())
    table = lancedb.connect(str(destination)).create_table("images", data=batches, mode="create")
    if table.count_rows() != total or len(samples) != config.query_count:
        raise ValueError("Snapshot or query-sample count mismatch")
    return table, samples


def search(table, vector, column: str, config: BenchmarkConfig, *, exact: bool):
    # Match the backend's cosine metric and materialize the full result before
    # stopping the timer. No plotting, model inference, or HTTP is involved.
    query = (
        table.search(vector, vector_column_name=column).distance_type("cosine").limit(config.top_k)
    )
    if exact:
        query = query.bypass_vector_index()
    else:
        if config.nprobes is not None:
            query = query.nprobes(config.nprobes)
        if config.refine_factor is not None:
            query = query.refine_factor(config.refine_factor)
    return query.to_arrow()


def create_index(table, column: str, index_type: str, config: BenchmarkConfig) -> float:
    options = {"distance_type": "cosine", "num_partitions": config.num_partitions}
    if index_type == "IVF_PQ":
        index = IvfPq(**options, num_sub_vectors=config.pq_sub_vectors)
    elif index_type == "IVF_HNSW_PQ":
        index = HnswPq(**options, num_sub_vectors=config.hnsw_pq_sub_vectors)
    else:
        index = HnswSq(**options)
    started = time.perf_counter()
    table.create_index(column, config=index, replace=True, name=f"benchmark_{column}")
    elapsed = time.perf_counter() - started
    stats = table.index_stats(f"benchmark_{column}")
    if stats is None or stats.num_unindexed_rows:
        raise RuntimeError(f"Incomplete index on {column}; refusing to report misleading timings")
    return elapsed


def measure(
    table,
    samples: list,
    truth: list[set],
    column: str,
    label: str,
    config: BenchmarkConfig,
    build_seconds: float = 0.0,
):
    exact = label == "No Index (baseline)"
    for sample in samples[: config.warmup_queries]:
        search(table, sample[column], column, config, exact=exact)
    observations = []
    rng = np.random.default_rng(config.seed)
    for repetition in range(config.repeats):
        for position in rng.permutation(len(samples)):
            sample = samples[position]
            started = time.perf_counter()
            result = search(table, sample[column], column, config, exact=exact)
            elapsed = (time.perf_counter() - started) * 1000
            found = set(result.column("img_id").to_pylist())
            observations.append(
                {
                    "index": label,
                    "model": column.removesuffix("_embeddings").upper(),
                    "vector_column": column,
                    "query_img_id": sample["img_id"],
                    "repeat": repetition,
                    "latency_ms": elapsed,
                    f"recall@{config.top_k}": len(found & truth[position]) / len(truth[position]),
                }
            )
    frame = pd.DataFrame(observations)
    latency = frame["latency_ms"]
    recall_key = f"recall@{config.top_k}"
    summary = {
        "index": label,
        "model": column.removesuffix("_embeddings").upper(),
        "vector_column": column,
        "avg_ms": float(latency.mean()),
        "p50_ms": float(latency.quantile(0.5)),
        "p95_ms": float(latency.quantile(0.95)),
        "total_ms": float(latency.sum()),
        "qps": len(frame) * 1000 / latency.sum(),
        recall_key: float(frame[recall_key].mean()),
        "build_seconds": build_seconds,
        "query_count": len(samples),
        "repeats": config.repeats,
        "metric": "cosine",
        "nprobes": config.nprobes,
        "refine_factor": config.refine_factor,
    }
    return summary, frame


def recommend(results: pd.DataFrame, config: BenchmarkConfig) -> pd.DataFrame:
    """Report eligible fastest candidates per column, without applying an index."""
    rows = []
    for column, group in results.groupby("vector_column", sort=True):
        eligible = group.loc[group[f"recall@{config.top_k}"] >= config.recall_threshold]
        if eligible.empty:
            rows.append(
                {
                    "vector_column": column,
                    "index": None,
                    "reason": "No candidate meets recall threshold",
                }
            )
        else:
            best = eligible.sort_values(["avg_ms", "index"]).iloc[0]
            rows.append(
                {
                    "vector_column": column,
                    "index": best["index"],
                    "avg_ms": best["avg_ms"],
                    f"recall@{config.top_k}": best[f"recall@{config.top_k}"],
                    "reason": "Fastest measured candidate meeting recall threshold",
                }
            )
    return pd.DataFrame(rows)


def run_benchmark(settings: SourceSettings, config: BenchmarkConfig):
    """Create a new retained scratch run; never modify source indexes or plotting data."""
    source = open_source(settings)
    total, dimensions = validate_source(source, config)
    # The public workflow writes only beneath the analyses directory containing this module.
    analyses = Path(__file__).resolve().parents[1]
    if not settings.runs.resolve().is_relative_to(analyses):
        raise ValueError("Benchmark outputs must stay within analyses/")
    if settings.runs.resolve().is_relative_to(settings.database.resolve()):
        raise ValueError("Benchmark output cannot be inside the source database")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    run_dir = settings.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "running",
        "source_database": str(settings.database),
        "source_table": settings.table,
        "source_version": source.version,
        "source_rows": total,
        "dimensions": dimensions,
        "config": asdict(config),
        "lancedb_version": lancedb.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "metric": "cosine",
        "scope": "Sequential warm-cache vector retrieval on an isolated full-table copy; includes self matches",
    }
    manifest_path = run_dir / "run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        table, samples = copy_for_benchmark(source, run_dir / "scratch.lance", config, total)
        manifest["query_img_ids"] = [sample["img_id"] for sample in samples]
        results, details = [], []
        for column in config.vector_columns:
            truth = [
                set(
                    search(table, sample[column], column, config, exact=True)
                    .column("img_id")
                    .to_pylist()
                )
                for sample in samples
            ]
            if any(len(ids) != config.top_k for ids in truth):
                raise ValueError("Exact search did not return top_k distinct image IDs")
            for label in ("No Index (baseline)", *config.index_types):
                build_seconds = (
                    0.0
                    if label == "No Index (baseline)"
                    else create_index(table, column, label, config)
                )
                summary, observations = measure(
                    table, samples, truth, column, label, config, build_seconds
                )
                results.append(summary)
                details.append(observations)
                # Preserve completed candidates even if a later build fails.
                pd.DataFrame(results).to_csv(run_dir / "indexing_benchmark.csv", index=False)
                pd.concat(details, ignore_index=True).to_csv(
                    run_dir / "query_timings.csv", index=False
                )
        frame = pd.DataFrame(results)
        recommendations = recommend(frame, config)
        recommendations.to_csv(run_dir / "recommendations.csv", index=False)
        manifest["status"] = "complete"
        return frame, recommendations, run_dir
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        raise
    finally:
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
