"""One morphospace run: labels, two streaming passes, scopes, metrics, artifact.

The embeddings (≈600k × 768) are never held in memory at once. The first pass
sums them into species × side centroids. The PCAs are fitted on those
centroids. The second pass revisits every image to measure how far it sits
from its centroid and where it falls in each scope's space, keeping only a few
numbers per image for the aggregations that follow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import polars as pl
from harmonize_core.errors import SourceValidationError
from harmonize_core.outputs import describe_artifact
from harmonize_core.progress import RunReporter
from harmonize_core.reports import run_directory, update_latest

from morphospace import __version__
from morphospace.groups import CentroidAccumulator, Groups, build_groups
from morphospace.models import MorphospaceParameters, MorphospaceRunManifest
from morphospace.outputs import MorphospaceOutputRepository
from morphospace.sources import iter_embeddings, load_labels, open_embeddings, table_version
from morphospace.space import (
    RANKS,
    Scope,
    ScopeSpace,
    enumerate_scopes,
    fit_space,
    project_rank,
    scope_lookup,
)
from morphospace.tables import (
    POINT_SCHEMA,
    conform,
    ellipse_stats,
    extremes_table,
    group_stats,
    kept_groups,
    points_frame,
    scope_metrics,
    species_table,
)

REPORT_KIND = "morphospace"
STEPS = 7


@dataclass(frozen=True)
class RunResult:
    run_id: str
    output_dir: Path
    database_path: Path
    manifest_path: Path
    counts: dict[str, int]
    runtime_seconds: float


def execute_run(
    *,
    database: Path,
    lance_dir: Path,
    lance_table: str,
    parameters: MorphospaceParameters,
    reports_dir: Path | None,
    output: Path | None,
    image_table: str = "image_meta",
    taxonomy_table: str = "image_meta_taxonomy",
    force: bool = False,
) -> RunResult:
    started = datetime.now(UTC)
    timer = perf_counter()
    progress = RunReporter(total_steps=STEPS)
    run_id = str(uuid.uuid4())
    if output is None:
        if reports_dir is None:
            raise SourceValidationError("Pass --output or --reports-dir.")
        output = run_directory(reports_dir, REPORT_KIND, run_id)
    rng = np.random.default_rng(parameters.seed)

    with progress.step("Read image sides and harmonized taxa"):
        labels = load_labels(
            database,
            image_table=image_table,
            taxonomy_table=taxonomy_table,
            exclude_families=parameters.exclude_families,
        )
        if len(labels) == 0:
            raise SourceValidationError("No image has a side and a matched accepted species.")
        groups = build_groups(labels)
        table = open_embeddings(lance_dir, lance_table)

    with progress.step("Pass 1: species × side centroids"):
        accumulator = first_pass(table, groups, parameters)
        centroids, keep = accumulator.centroids(parameters.min_images)

    with progress.step("Fit shared dorso-ventral PCA per scope"):
        scopes = enumerate_scopes(groups, keep, min_species=parameters.min_scope_species)
        spaces = {
            rank: [fit_space(scope, groups, centroids) for scope in members]
            for rank, members in scopes.items()
        }

    with progress.step("Pass 2: intraspecific dispersion, medoids and ellipses"):
        images = second_pass(table, groups, keep, centroids, scopes, spaces, parameters)

    with progress.step("Disparity and dorso-ventral correlation"):
        tables = build_tables(
            run_id,
            groups,
            accumulator.counts,
            keep,
            centroids,
            scopes,
            spaces,
            images,
            parameters,
            rng,
        )

    repository = MorphospaceOutputRepository(output)
    with (
        progress.step("Write artifact database"),
        repository.build_database(force=force) as connection,
    ):
        for name, frame in tables.items():
            connection.register("staging", frame.to_arrow())
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM staging')
            connection.unregister("staging")

    with progress.step("Write manifest"):
        completed = datetime.now(UTC)
        runtime = perf_counter() - timer
        counts = {
            "labelled_images": len(labels),
            "embedded_images": int(accumulator.embedded),
            "groups": int(keep.sum()),
            "species": len(np.unique(groups.group_species[keep])),
            **{f"scopes_{rank}": len(members) for rank, members in scopes.items()},
            **{f"rows_{name}": frame.height for name, frame in tables.items()},
        }
        manifest = MorphospaceRunManifest(
            run_id=run_id,
            package_version=__version__,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            runtime_seconds=round(runtime, 3),
            source_database=str(database.resolve()),
            lance_database=str(lance_dir.resolve()),
            lance_table=lance_table,
            lance_version=table_version(table),
            parameters=parameters,
            outputs={
                "database": str(repository.database_path.resolve()),
                "manifest": str(repository.manifest_path.resolve()),
            },
            artifacts=[describe_artifact("database", repository.database_path)],
            counts=counts,
        )
        repository.write_manifest(manifest, force=force)
        if reports_dir is not None and output.resolve().is_relative_to(reports_dir.resolve()):
            update_latest(
                reports_dir,
                REPORT_KIND,
                run_id=run_id,
                completed_at=completed.isoformat(),
                manifest=repository.manifest_path,
            )
    return RunResult(
        run_id=run_id,
        output_dir=output,
        database_path=repository.database_path,
        manifest_path=repository.manifest_path,
        counts=counts,
        runtime_seconds=runtime,
    )


def first_pass(table, groups: Groups, parameters: MorphospaceParameters) -> CentroidAccumulator:
    """Species × side vector sums and image counts."""
    accumulator: CentroidAccumulator | None = None
    
    for ids, vectors in iter_embeddings(
        table, parameters.embedding_column, batch_size=parameters.batch_size
    ):
        if accumulator is None:
            accumulator = CentroidAccumulator(groups, vectors.shape[1])
        accumulator.add(ids, vectors)

    if accumulator is None or accumulator.embedded == 0:
        raise SourceValidationError("No labelled image has an embedding.")
    
    return accumulator


def second_pass(
    table,
    groups: Groups,
    keep: np.ndarray,
    centroids: np.ndarray,
    scopes: dict[str, list[Scope]],
    spaces: dict[str, list[ScopeSpace]],
    parameters: MorphospaceParameters,
) -> pl.DataFrame:
    """Per kept image: its similarity to its centroid and PC1/PC2 in each rank's scope.

    The PC columns are NaN for an image whose species is in no scope of that rank.
    """
    group_species = groups.group_species
    lookups = {rank: scope_lookup(scopes[rank], groups.taxa.height) for rank in RANKS}
    frames: list[pl.DataFrame] = []

    for ids, vectors in iter_embeddings(
        table, parameters.embedding_column, batch_size=parameters.batch_size
    ):
        matched = groups.lookup(ids)
        matched = matched.filter(pl.Series(keep[matched["group_id"].to_numpy()]))
        if matched.height == 0:
            continue
        group_ids = matched["group_id"].to_numpy()
        usable = vectors[matched["row"].to_numpy()]
        columns: dict[str, object] = {
            "img_id": matched["img_id"],
            "group_id": group_ids,
            "similarity": np.einsum("ij,ij->i", usable, centroids[group_ids]).astype(np.float64),
        }
        species = group_species[group_ids]
        for rank in RANKS:
            xy = project_rank(spaces[rank], lookups[rank][species], usable)
            columns[f"{rank}_x"], columns[f"{rank}_y"] = xy[:, 0], xy[:, 1]
        frames.append(pl.DataFrame(columns))

    return pl.concat(frames)


def build_tables(
    run_id: str,
    groups: Groups,
    counts: np.ndarray,
    keep: np.ndarray,
    centroids: np.ndarray,
    scopes: dict[str, list[Scope]],
    spaces: dict[str, list[ScopeSpace]],
    images: pl.DataFrame,
    parameters: MorphospaceParameters,
    rng: np.random.Generator,
) -> dict[str, pl.DataFrame]:
    
    side_groups = groups.side_groups(keep)
    kept = kept_groups(groups, counts, keep, group_stats(images))
    points = points_frame(groups, kept, centroids, scopes, spaces, ellipse_stats(images))
    scope, disparity = scope_metrics(
        run_id, groups, centroids, scopes, spaces, side_groups, parameters, rng
    )

    return {
        "scope": scope,
        "points": conform(points, POINT_SCHEMA),
        "species": species_table(groups, kept, centroids, side_groups),
        "disparity": disparity,
        "extremes": extremes_table(points, scope),
    }
