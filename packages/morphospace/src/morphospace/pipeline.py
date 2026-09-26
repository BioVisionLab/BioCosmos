"""One morphospace run: labels, two streaming passes, scopes, metrics, artifact.

The embeddings (≈600k × 768) are never held in memory at once. The first pass
sums them into species × side centroids. The PCAs are fitted on those
centroids. The second pass revisits every image to measure how far it sits
from its centroid and where it falls in each scope's space.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import pyarrow as pa
from harmonize_core.errors import SourceValidationError
from harmonize_core.outputs import describe_artifact
from harmonize_core.progress import RunReporter
from harmonize_core.reports import run_directory, update_latest

from morphospace import __version__
from morphospace.centroids import CentroidAccumulator, GroupIndex, build_index
from morphospace.disparity import disparity, dorso_ventral_divergence, mantel
from morphospace.models import SIDES, MorphospaceParameters, MorphospaceRunManifest
from morphospace.outputs import MorphospaceOutputRepository
from morphospace.sources import iter_embeddings, load_labels, open_embeddings, table_version
from morphospace.space import EllipseAccumulator, Scope, enumerate_scopes, fit

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


class MedoidTracker:
    """Per group: the image closest to the centroid, and the summed distance to it."""

    def __init__(self, size: int) -> None:
        self.best = np.full(size, -np.inf)
        self.best_id = np.full(size, None, dtype=object)
        self.distance = np.zeros(size)

    def add(self, groups: np.ndarray, img_ids: np.ndarray, similarity: np.ndarray) -> None:
        self.distance += np.bincount(groups, weights=1.0 - similarity, minlength=len(self.best))
        order = np.lexsort((-similarity, groups))
        first = order[np.r_[True, groups[order][1:] != groups[order][:-1]]]
        better = similarity[first] > self.best[groups[first]]
        winners = first[better]
        self.best[groups[winners]] = similarity[winners]
        self.best_id[groups[winners]] = img_ids[winners]


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
        labels = load_labels(database, image_table=image_table, taxonomy_table=taxonomy_table)
        if len(labels) == 0:
            raise SourceValidationError("No image has a side and a matched accepted species.")
        index = build_index(labels)
        table = open_embeddings(lance_dir, lance_table)

    with progress.step("Pass 1: species × side centroids"):
        accumulator: CentroidAccumulator | None = None
        for ids, vectors in iter_embeddings(
            table, parameters.embedding_column, batch_size=parameters.batch_size
        ):
            if accumulator is None:
                accumulator = CentroidAccumulator(index, vectors.shape[1])
            accumulator.add(ids, vectors)
        if accumulator is None or accumulator.embedded == 0:
            raise SourceValidationError("No labelled image has an embedding.")
        centroids, keep = accumulator.centroids(parameters.min_images)

    with progress.step("Fit shared dorso-ventral PCA per scope"):
        scopes = enumerate_scopes(index, keep, min_species=parameters.min_scope_species)
        for members in scopes.values():
            for scope in members:
                fit(scope, index, centroids)

    with progress.step("Pass 2: intraspecific dispersion, medoids and ellipses"):
        medoids = MedoidTracker(index.size)
        ellipses = EllipseAccumulator(index, scopes)
        for ids, vectors in iter_embeddings(
            table, parameters.embedding_column, batch_size=parameters.batch_size
        ):
            groups = index.lookup(ids)
            usable = groups >= 0
            usable[usable] = keep[groups[usable]]
            if not usable.any():
                continue
            groups, ids, vectors = groups[usable], ids[usable], vectors[usable]
            similarity = np.einsum("ij,ij->i", vectors, centroids[groups])
            medoids.add(groups, ids, similarity)
            ellipses.add(groups, vectors)

    with progress.step("Disparity and dorso-ventral integration"):
        tables = _build_tables(
            run_id,
            index,
            accumulator.counts,
            keep,
            centroids,
            scopes,
            medoids,
            ellipses,
            parameters,
            rng,
        )

    repository = MorphospaceOutputRepository(output)
    with (
        progress.step("Write artifact database"),
        repository.build_database(force=force) as connection,
    ):
        for name, arrow in tables.items():
            connection.register("staging", arrow)
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM staging')
            connection.unregister("staging")

    with progress.step("Write manifest"):
        completed = datetime.now(UTC)
        runtime = perf_counter() - timer
        counts = {
            "labelled_images": len(labels),
            "embedded_images": int(accumulator.embedded),
            "groups": int(keep.sum()),
            "species": len(np.unique(index.group_species[keep])),
            **{f"scopes_{rank}": len(members) for rank, members in scopes.items()},
            **{f"rows_{name}": arrow.num_rows for name, arrow in tables.items()},
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


def _text(value) -> str | None:
    return None if value is None or value == "" else str(value)


def _build_tables(
    run_id: str,
    index: GroupIndex,
    counts: np.ndarray,
    keep: np.ndarray,
    centroids: np.ndarray,
    scopes: dict[str, list[Scope]],
    medoids: MedoidTracker,
    ellipses: EllipseAccumulator,
    parameters: MorphospaceParameters,
    rng: np.random.Generator,
) -> dict[str, pa.Table]:
    taxa = index.taxa
    group_of: dict[tuple[int, int], int] = {
        (int(s), int(side)): g
        for g, (s, side) in enumerate(zip(index.group_species, index.group_side, strict=True))
        if keep[g]
    }
    dispersion = np.where(counts > 0, medoids.distance / np.maximum(counts, 1), np.nan)

    # Species: one row each, both sides side by side.
    species_rows: list[dict] = []
    for s in np.unique(index.group_species[keep]):
        row: dict = {
            "accepted_species": str(taxa.accepted_species[s]),
            "page_key": _text(taxa.page_key[s]),
            "genus_key": _text(taxa.genus_key[s]),
            "genus_name": _text(taxa.genus_name[s]),
            "family_key": _text(taxa.family_key[s]),
            "family_name": _text(taxa.family_name[s]),
        }
        for side_number, side in enumerate(SIDES):
            g = group_of.get((int(s), side_number))
            row[f"{side}_n"] = int(counts[g]) if g is not None else None
            row[f"{side}_dispersion"] = float(dispersion[g]) if g is not None else None
            row[f"{side}_img_id"] = medoids.best_id[g] if g is not None else None
        dorsal, ventral = group_of.get((int(s), 0)), group_of.get((int(s), 1))
        row["dv_divergence"] = (
            float(dorso_ventral_divergence(centroids[[dorsal]], centroids[[ventral]])[0])
            if dorsal is not None and ventral is not None
            else None
        )
        species_rows.append(row)

    scope_rows: list[dict] = []
    point_rows: list[dict] = []
    disparity_rows: list[dict] = []
    extreme_rows: list[dict] = []
    for rank, members in scopes.items():
        for scope in members:
            groups = scope.groups
            projected = scope.project(centroids[groups])
            key = {"scope_rank": rank, "scope_key": scope.key}
            for g, coords in zip(groups, projected, strict=True):
                s = int(index.group_species[g])
                mx, my, sx, sy, rho = ellipses.ellipse(rank, int(g))
                point_rows.append(
                    {
                        **key,
                        "accepted_species": str(taxa.accepted_species[s]),
                        "page_key": _text(taxa.page_key[s]),
                        "genus_key": _text(taxa.genus_key[s]),
                        "family_key": _text(taxa.family_key[s]),
                        "side": SIDES[int(index.group_side[g])],
                        "n_images": int(counts[g]),
                        "pc1": float(coords[0]),
                        "pc2": float(coords[1]),
                        "pc3": float(coords[2]),
                        "ell_x": mx,
                        "ell_y": my,
                        "ell_sx": sx,
                        "ell_sy": sy,
                        "ell_rho": rho,
                        "img_id": medoids.best_id[g],
                    }
                )
            for axis in range(projected.shape[1]):
                if scope.explained[axis] == 0:
                    continue
                ends = (("min", projected[:, axis].argmin()), ("max", projected[:, axis].argmax()))
                for end, position in ends:
                    g = int(groups[position])
                    s = int(index.group_species[g])
                    extreme_rows.append(
                        {
                            **key,
                            "axis": f"pc{axis + 1}",
                            "end": end,
                            "accepted_species": str(taxa.accepted_species[s]),
                            "page_key": _text(taxa.page_key[s]),
                            "side": SIDES[int(index.group_side[g])],
                            "img_id": medoids.best_id[g],
                            "value": float(projected[position, axis]),
                        }
                    )

            for side_number, side in enumerate(SIDES):
                side_groups = groups[index.group_side[groups] == side_number]
                result = disparity(
                    centroids[side_groups],
                    k=parameters.rarefy_k,
                    reps=parameters.bootstrap,
                    rng=rng,
                )
                disparity_rows.append(
                    {
                        **key,
                        "side": side,
                        "n_species": result.n_species,
                        "sum_var": result.sum_var,
                        "rarefied_mean": result.rarefied_mean,
                        "rarefied_low": result.rarefied_low,
                        "rarefied_high": result.rarefied_high,
                        "rarefy_k": parameters.rarefy_k,
                    }
                )

            paired = [
                (group_of[(int(s), 0)], group_of[(int(s), 1)])
                for s in scope.species
                if (int(s), 0) in group_of and (int(s), 1) in group_of
            ]
            integration = None
            if len(paired) >= parameters.mantel_min_species:
                pairs = np.array(paired)
                dorsal_groups, ventral_groups = pairs[:, 0], pairs[:, 1]
                integration = mantel(
                    centroids[dorsal_groups],
                    centroids[ventral_groups],
                    permutations=parameters.permutations,
                    rng=rng,
                    max_species=parameters.mantel_max_species,
                    permutation_max_species=parameters.permutation_max_species,
                )
            scope_rows.append(
                {
                    **key,
                    "scope_name": scope.name,
                    "parent_family": _text(scope.parent_family),
                    "n_species": len(scope.species),
                    "n_species_both": len(paired),
                    "basis": scope.basis,
                    "explained_pc1": float(scope.explained[0]),
                    "explained_pc2": float(scope.explained[1]),
                    "explained_pc3": float(scope.explained[2]),
                    "dv_mantel_n": integration.n_species if integration else len(paired),
                    "dv_mantel_r": integration.r if integration else None,
                    "dv_mantel_p": integration.p if integration else None,
                    "run_id": run_id,
                }
            )

    return {
        "scope": _arrow(scope_rows, SCOPE_SCHEMA),
        "points": _arrow(point_rows, POINT_SCHEMA),
        "species": _arrow(species_rows, SPECIES_SCHEMA),
        "disparity": _arrow(disparity_rows, DISPARITY_SCHEMA),
        "extremes": _arrow(extreme_rows, EXTREME_SCHEMA),
    }


def _arrow(rows: list[dict], schema: pa.Schema) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


_S, _F, _I = pa.string(), pa.float64(), pa.int64()
_SCOPE_KEY = [("scope_rank", _S), ("scope_key", _S)]

SCOPE_SCHEMA = pa.schema(
    _SCOPE_KEY
    + [
        ("scope_name", _S),
        ("parent_family", _S),
        ("n_species", _I),
        ("n_species_both", _I),
        ("basis", _S),
        ("explained_pc1", _F),
        ("explained_pc2", _F),
        ("explained_pc3", _F),
        ("dv_mantel_n", _I),
        ("dv_mantel_r", _F),
        ("dv_mantel_p", _F),
        ("run_id", _S),
    ]
)
POINT_SCHEMA = pa.schema(
    _SCOPE_KEY
    + [
        ("accepted_species", _S),
        ("page_key", _S),
        ("genus_key", _S),
        ("family_key", _S),
        ("side", _S),
        ("n_images", _I),
        ("pc1", _F),
        ("pc2", _F),
        ("pc3", _F),
        ("ell_x", _F),
        ("ell_y", _F),
        ("ell_sx", _F),
        ("ell_sy", _F),
        ("ell_rho", _F),
        ("img_id", _S),
    ]
)
SPECIES_SCHEMA = pa.schema(
    [
        ("accepted_species", _S),
        ("page_key", _S),
        ("genus_key", _S),
        ("genus_name", _S),
        ("family_key", _S),
        ("family_name", _S),
    ]
    + [
        (f"{side}_{column}", kind)
        for side in SIDES
        for column, kind in (("n", _I), ("dispersion", _F), ("img_id", _S))
    ]
    + [("dv_divergence", _F)]
)
DISPARITY_SCHEMA = pa.schema(
    _SCOPE_KEY
    + [
        ("side", _S),
        ("n_species", _I),
        ("sum_var", _F),
        ("rarefied_mean", _F),
        ("rarefied_low", _F),
        ("rarefied_high", _F),
        ("rarefy_k", _I),
    ]
)
EXTREME_SCHEMA = pa.schema(
    _SCOPE_KEY
    + [
        ("axis", _S),
        ("end", _S),
        ("accepted_species", _S),
        ("page_key", _S),
        ("side", _S),
        ("img_id", _S),
        ("value", _F),
    ]
)
