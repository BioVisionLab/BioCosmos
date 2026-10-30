"""Benchmark cosine vector indexes on an isolated copy of the backend Lance table.

Each index is built once and searched over a grid of query-time settings (`nprobes`,
HNSW `ef`, `refine_factor`), because recall and latency depend on how an index is
searched as much as on the index itself. Query images are held out of the searched
copy, and recall@k is judged against exact cosine distances, ties included.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import platform
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
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
HNSW_TYPES = ("IVF_HNSW_SQ", "IVF_HNSW_PQ")
BASELINE = "No Index (baseline)"
# The public workflow writes only beneath the analyses directory containing this module.
ANALYSES = Path(__file__).resolve().parents[1]
# The exact reference fetches this many rows past top_k, so images tied with the k-th
# nearest are found and accepted as hits.
TIE_MARGIN = 10
TIE_TOLERANCE = 1e-6

# Copied from `vector_index_config` in backend/app/database/lance.py, so "auto" builds
# the index the backend builds. Copied rather than imported: this module never imports
# backend code.
BACKEND_MAX_PARTITIONS = 4_096
BACKEND_MIN_ROWS_FOR_INDEX = 5_000
BACKEND_DIMS_PER_SUB_VECTOR = 8

Auto = Literal["auto"]


@dataclass(frozen=True)
class SearchSetting:
    """Query-time controls; None leaves LanceDB's default."""

    nprobes: int | None = None
    ef: int | None = None
    refine_factor: int | None = None


# The backend's search (`NPROBES`, `REFINE_FACTOR` in backend/app/services/images.py).
PRODUCTION_SEARCH = SearchSetting(nprobes=20, refine_factor=10)


@dataclass(frozen=True)
class BuildParameters:
    num_partitions: int
    pq_sub_vectors: int
    hnsw_pq_sub_vectors: int


@dataclass(frozen=True)
class SourceSettings:
    database: Path
    table: str
    runs: Path


@dataclass(frozen=True)
class BenchmarkConfig:
    query_count: int = 300
    repeats: int = 3
    warmup_queries: int = 10
    top_k: int = 10
    seed: int = 42
    num_partitions: int | Auto = "auto"
    pq_sub_vectors: int | Auto = "auto"
    hnsw_pq_sub_vectors: int | Auto = "auto"
    nprobes_grid: tuple[int | None, ...] = (5, 10, 20, 40, 80, 160)
    ef_grid: tuple[int | None, ...] = (None, 20, 40, 80, 160)
    refine_grid: tuple[int | None, ...] = (None, 2, 5, 10, 20)
    production: SearchSetting = field(default=PRODUCTION_SEARCH)
    index_types: tuple[str, ...] = INDEX_TYPES
    vector_columns: tuple[str, ...] = VECTOR_COLUMNS
    recall_threshold: float = 0.95
    bootstrap: int = 1_000

    def __post_init__(self):
        for name in ("query_count", "repeats", "top_k", "bootstrap"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")

        for name in ("num_partitions", "pq_sub_vectors", "hnsw_pq_sub_vectors"):
            value = getattr(self, name)

            if value != "auto" and (not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive integer or 'auto'")

        if self.warmup_queries < 0 or self.seed < 0:
            raise ValueError("warmup_queries and seed must be nonnegative")

        if not 0 <= self.recall_threshold <= 1:
            raise ValueError("recall_threshold must lie between zero and one")

        for name in ("nprobes_grid", "ef_grid", "refine_grid"):
            grid = getattr(self, name)

            if not grid or len(set(grid)) != len(grid):
                raise ValueError(f"{name} must hold at least one distinct value")

            if any(value is not None and value < 1 for value in grid):
                raise ValueError(f"{name} values must be positive or None")

        if any(value is not None and value < 1 for value in asdict(self.production).values()):
            raise ValueError("production search values must be positive or None")

        if any(value is not None and value < self.top_k for value in self.ef_grid):
            raise ValueError("ef values must be at least top_k")

        if not self.vector_columns or len(set(self.vector_columns)) != len(self.vector_columns):
            raise ValueError("Select at least one distinct vector column")

        if not set(self.vector_columns) <= set(VECTOR_COLUMNS):
            raise ValueError(f"Select backend embedding columns from {VECTOR_COLUMNS}")

        if len(set(self.index_types)) != len(self.index_types) or not set(self.index_types) <= set(
            INDEX_TYPES
        ):
            raise ValueError(f"Select distinct index types from {INDEX_TYPES}")


def build_parameters(rows: int, dims: int, config: BenchmarkConfig) -> BuildParameters:
    """Resolve "auto" build settings with the backend's rule for this table size."""

    partitions = config.num_partitions

    if partitions == "auto":
        partitions = min(
            BACKEND_MAX_PARTITIONS, int(math.sqrt(max(rows, BACKEND_MIN_ROWS_FOR_INDEX)))
        )

    backend_sub_vectors = max(1, dims // BACKEND_DIMS_PER_SUB_VECTOR)
    pq = backend_sub_vectors if config.pq_sub_vectors == "auto" else config.pq_sub_vectors
    hnsw_pq = (
        backend_sub_vectors if config.hnsw_pq_sub_vectors == "auto" else config.hnsw_pq_sub_vectors
    )

    return BuildParameters(partitions, pq, hnsw_pq)


def search_settings(
    index_type: str, num_partitions: int, config: BenchmarkConfig
) -> list[SearchSetting]:
    """Every grid combination valid for this index, with the production setting included.

    `ef` only steers HNSW, so other indexes search with its default alone. Probing more
    partitions than the index has is dropped, and so is an `ef` below the candidates the
    search fetches (`top_k` times `refine_factor`), which LanceDB rejects.
    """

    if index_type == BASELINE:
        return [SearchSetting()]

    ef_grid = config.ef_grid if index_type in HNSW_TYPES else (None,)
    settings = [
        SearchSetting(nprobes, ef, refine)
        for nprobes, ef, refine in itertools.product(
            config.nprobes_grid, ef_grid, config.refine_grid
        )
        if (nprobes is None or nprobes <= num_partitions)
        and (ef is None or ef >= config.top_k * (refine or 1))
    ]

    if config.production not in settings:
        settings.append(config.production)

    return list(dict.fromkeys(settings))


def recall_at_k(found_ids, accepted_ids: set, k: int) -> float:
    """Share of the k results that are true neighbors, counting ties with the k-th."""

    return min(len(set(found_ids) & accepted_ids), k) / k


def accepted_neighbors(ids: list, distances: list[float], k: int) -> set:
    """IDs no farther than the k-th exact neighbor, so an equally near image is a hit."""

    if len(ids) < k:
        raise ValueError("Exact search did not return top_k image IDs")

    cutoff = sorted(distances)[k - 1] + TIE_TOLERANCE

    return {img_id for img_id, distance in zip(ids, distances, strict=True) if distance <= cutoff}


def bootstrap_interval(values, resamples: int, seed: int) -> tuple[float, float]:
    """A 95% percentile interval for the mean, resampling queries."""

    values = np.asarray(values, dtype=float)
    draws = np.random.default_rng(seed).integers(0, len(values), size=(resamples, len(values)))
    means = values[draws].mean(axis=1)

    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


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
    searched = total - config.query_count

    if config.query_count >= total or searched <= config.top_k:
        raise ValueError("The source needs more than top_k rows beyond the held-out queries")

    if "img_id" not in table.schema.names:
        raise ValueError("Source table requires stable img_id values")

    dimensions = {}

    for column in config.vector_columns:
        if column not in table.schema.names:
            raise ValueError(f"Missing backend embedding column: {column}")

        field_type = table.schema.field(column).type

        if not pa.types.is_fixed_size_list(field_type):
            raise ValueError(f"{column} must contain fixed-size embedding vectors")

        dimensions[column] = field_type.list_size
        build = build_parameters(searched, dimensions[column], config)

        for index_type, subvectors in (
            ("IVF_PQ", build.pq_sub_vectors),
            ("IVF_HNSW_PQ", build.hnsw_pq_sub_vectors),
        ):
            if index_type in config.index_types and dimensions[column] % subvectors:
                raise ValueError(
                    f"{column} dimension must be divisible by {subvectors} for {index_type}"
                )

        if config.index_types and searched < max(256, build.num_partitions):
            raise ValueError(
                "ANN training needs at least 256 rows and at least num_partitions rows"
            )

    return total, dimensions


def checked_batches(reader, positions: set, samples: list, columns: tuple[str, ...], total: int):
    """Validate each source batch, move the query rows into `samples`, yield the rest."""

    offset = 0
    seen_ids = set()

    for batch in reader:
        ids = batch.column("img_id").to_pylist()

        if any(not isinstance(value, str) or not value.strip() for value in ids):
            raise ValueError("img_id must contain nonblank strings")

        if len(set(ids)) != len(ids) or seen_ids.intersection(ids):
            raise ValueError("img_id must be unique for recall calculations")

        seen_ids.update(ids)

        for column in columns:
            values = np.asarray(batch.column(column).to_pylist(), dtype=np.float32)

            if (
                values.ndim != 2
                or not np.isfinite(values).all()
                or np.any(np.linalg.norm(values, axis=1) == 0)
            ):
                raise ValueError(f"{column} contains missing, nonfinite, or zero-norm vectors")

        held_out = np.array([offset + local in positions for local in range(len(batch))])

        for local in np.flatnonzero(held_out):
            samples.append(batch.slice(int(local), 1).to_pylist()[0])

        offset += len(batch)

        if (~held_out).any():
            yield batch.filter(pa.array(~held_out))

    if offset != total:
        raise ValueError("Copied row count differs from the pinned source count")


def copy_for_benchmark(source, destination: Path, config: BenchmarkConfig, total: int):
    """Stream the pinned source to a fresh table, holding the seeded query rows out of it."""

    positions = set(
        np.random.default_rng(config.seed).choice(total, config.query_count, replace=False).tolist()
    )
    samples = []
    reader = source.search().limit(None).to_batches(batch_size=1024)
    batches = pa.RecordBatchReader.from_batches(
        reader.schema,
        checked_batches(reader, positions, samples, config.vector_columns, total),
    )
    table = lancedb.connect(str(destination)).create_table("images", data=batches, mode="create")

    if table.count_rows() != total - config.query_count or len(samples) != config.query_count:
        raise ValueError("Snapshot or query-sample count mismatch")

    return table, samples


def search(
    table, vector, column: str, setting: SearchSetting, limit: int, *, exact: bool
) -> pa.Table:
    # Match the backend's cosine metric and projection, and materialize the result before
    # stopping the timer. No plotting, model inference, or HTTP is involved.
    query = (
        table.search(vector, vector_column_name=column)
        .distance_type("cosine")
        .select(["img_id", "_distance"])
        .limit(limit)
    )

    if exact:
        return query.bypass_vector_index().to_arrow()

    if setting.nprobes is not None:
        query = query.nprobes(setting.nprobes)

    if setting.ef is not None:
        query = query.ef(setting.ef)

    if setting.refine_factor is not None:
        query = query.refine_factor(setting.refine_factor)

    return query.to_arrow()


def exact_truth(table, samples: list, column: str, top_k: int) -> list[set]:
    truth = []

    for sample in samples:
        result = search(
            table, sample[column], column, SearchSetting(), top_k + TIE_MARGIN, exact=True
        )
        truth.append(
            accepted_neighbors(
                result.column("img_id").to_pylist(),
                result.column("_distance").to_pylist(),
                top_k,
            )
        )

    return truth


def create_index(table, column: str, index_type: str, build: BuildParameters) -> float:
    options = {"distance_type": "cosine", "num_partitions": build.num_partitions}

    if index_type == "IVF_PQ":
        index = IvfPq(**options, num_sub_vectors=build.pq_sub_vectors)
    elif index_type == "IVF_HNSW_PQ":
        index = HnswPq(**options, num_sub_vectors=build.hnsw_pq_sub_vectors)
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
    setting: SearchSetting,
    config: BenchmarkConfig,
    build_seconds: float = 0.0,
):
    exact = label == BASELINE
    model = column.removesuffix("_embeddings").upper()
    recall_key = f"recall@{config.top_k}"

    for sample in samples[: config.warmup_queries]:
        search(table, sample[column], column, setting, config.top_k, exact=exact)

    observations = []
    rng = np.random.default_rng(config.seed)

    for repetition in range(config.repeats):
        for position in rng.permutation(len(samples)):
            sample = samples[position]
            started = time.perf_counter()
            result = search(table, sample[column], column, setting, config.top_k, exact=exact)
            elapsed = (time.perf_counter() - started) * 1000
            observations.append(
                {
                    "index": label,
                    "model": model,
                    "vector_column": column,
                    **asdict(setting),
                    "query_img_id": sample["img_id"],
                    "repeat": repetition,
                    "latency_ms": elapsed,
                    recall_key: recall_at_k(
                        result.column("img_id").to_pylist(), truth[position], config.top_k
                    ),
                }
            )

    frame = pd.DataFrame(observations)
    latency = frame["latency_ms"]
    per_query = frame.groupby("query_img_id", sort=True)[recall_key].mean()
    recall_low, recall_high = bootstrap_interval(per_query, config.bootstrap, config.seed)
    summary = {
        "index": label,
        "model": model,
        "vector_column": column,
        **asdict(setting),
        "is_production": not exact and setting == config.production,
        "avg_ms": float(latency.mean()),
        "p50_ms": float(latency.quantile(0.5)),
        "p95_ms": float(latency.quantile(0.95)),
        "total_ms": float(latency.sum()),
        "qps": len(frame) * 1000 / latency.sum(),
        recall_key: float(frame[recall_key].mean()),
        "recall_low": recall_low,
        "recall_high": recall_high,
        "build_seconds": build_seconds,
        "query_count": len(samples),
        "repeats": config.repeats,
        "metric": "cosine",
    }

    return summary, frame


def recommend(results: pd.DataFrame, config: BenchmarkConfig) -> pd.DataFrame:
    """The fastest setting of each index reaching the recall threshold, per column.

    Comparing indexes at matched recall rather than at one setting each; advisory only,
    nothing is applied to the backend.
    """

    recall_key = f"recall@{config.top_k}"
    rows = []

    for (column, index), group in results.groupby(["vector_column", "index"], sort=True):
        eligible = group.loc[group[recall_key] >= config.recall_threshold]
        row = {"vector_column": column, "model": group["model"].iloc[0], "index": index}

        if eligible.empty:
            best = group.sort_values([recall_key, "avg_ms"], ascending=[False, True]).iloc[0]
            row["reason"] = "No setting reaches the recall threshold; highest recall shown"
        else:
            best = eligible.sort_values("avg_ms").iloc[0]
            row["reason"] = "Fastest setting reaching the recall threshold"

        for key in ("nprobes", "ef", "refine_factor", "avg_ms", "p95_ms", recall_key):
            row[key] = best[key]

        row["meets_threshold"] = not eligible.empty
        rows.append(row)

    return pd.DataFrame(rows)


def run_benchmark(settings: SourceSettings, config: BenchmarkConfig):
    """Create a new retained scratch run; never modify source indexes or plotting data."""

    source = open_source(settings)
    total, dimensions = validate_source(source, config)
    searched = total - config.query_count

    if not settings.runs.resolve().is_relative_to(ANALYSES):
        raise ValueError("Benchmark outputs must stay within analyses/")

    if settings.runs.resolve().is_relative_to(settings.database.resolve()):
        raise ValueError("Benchmark output cannot be inside the source database")

    builds = {
        column: build_parameters(searched, dims, config) for column, dims in dimensions.items()
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    run_dir = settings.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "running",
        "source_database": str(settings.database),
        "source_table": settings.table,
        "source_version": source.version,
        "source_rows": total,
        "searched_rows": searched,
        "dimensions": dimensions,
        "config": asdict(config),
        "build_parameters": {column: asdict(build) for column, build in builds.items()},
        "lancedb_version": lancedb.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "metric": "cosine",
        "scope": (
            "Sequential warm-cache vector retrieval on an isolated full-table copy with the "
            "query images held out; each index searched over a grid of query-time settings"
        ),
    }
    manifest_path = run_dir / "run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    try:
        table, samples = copy_for_benchmark(source, run_dir / "scratch.lance", config, total)
        manifest["query_img_ids"] = [sample["img_id"] for sample in samples]
        results, details = [], []

        for column in config.vector_columns:
            truth = exact_truth(table, samples, column, config.top_k)

            for label in (BASELINE, *config.index_types):
                build_seconds = (
                    0.0 if label == BASELINE else create_index(table, column, label, builds[column])
                )

                for setting in search_settings(label, builds[column].num_partitions, config):
                    summary, observations = measure(
                        table, samples, truth, column, label, setting, config, build_seconds
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
