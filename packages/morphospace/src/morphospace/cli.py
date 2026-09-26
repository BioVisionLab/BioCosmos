"""Command-line interface for morphospace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import duckdb
import numpy as np
import typer
from harmonize_core.errors import HarmonizeError, OutputError
from harmonize_core.progress import format_duration
from harmonize_core.reports import DEFAULT_REPORTS_DIR, LATEST_NAME

from morphospace.centroids import build_index
from morphospace.models import SIDES, MorphospaceParameters
from morphospace.outputs import DEFAULT_PREFIX, MorphospaceOutputRepository, default_destinations
from morphospace.pipeline import REPORT_KIND, execute_run
from morphospace.sources import load_labels

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

DbOption = Annotated[Path, typer.Option("--db", help="Backend DuckDB file (biocosmos.duckdb).")]
ImageTableOption = Annotated[str, typer.Option("--image-table")]
TaxonomyTableOption = Annotated[str, typer.Option("--taxonomy-table")]


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"Error: {exc}", err=True)
    return typer.Exit(code=2)


def _reports_dir(value: Path | None) -> Path | None:
    if value is not None:
        return value
    return DEFAULT_REPORTS_DIR if DEFAULT_REPORTS_DIR.is_dir() else None


@app.command("inspect")
def inspect_command(
    db: DbOption,
    image_table: ImageTableOption = "image_meta",
    taxonomy_table: TaxonomyTableOption = "image_meta_taxonomy",
    min_images: Annotated[int, typer.Option("--min-images")] = 3,
    min_scope_species: Annotated[int, typer.Option("--min-scope-species")] = 3,
) -> None:
    """Count what a run would cover, without reading any embedding."""
    try:
        labels = load_labels(
            db,
            image_table=image_table,
            taxonomy_table=taxonomy_table,
            exclude_families=MorphospaceParameters().exclude_families,
        )
    except HarmonizeError as exc:
        raise _fail(exc) from exc
    index = build_index(labels)
    counts = np.bincount(index.lookup(labels.img_id), minlength=index.size)
    keep = counts >= min_images
    typer.echo(f"Labelled images: {len(labels):,}")
    for number, side in enumerate(SIDES):
        on_side = index.group_side == number
        typer.echo(
            f"  {side}: {int(counts[on_side].sum()):,} images, "
            f"{int((on_side & keep).sum()):,} species with ≥{min_images} images"
        )
    kept_species = index.group_species[keep]
    species, sides = np.unique(kept_species, return_counts=True)
    typer.echo(f"Species kept: {len(species):,}; seen from both sides: {int((sides == 2).sum()):,}")
    for label, column in (("Families", index.taxa.family_key), ("Genera", index.taxa.genus_key)):
        keys = [k for k in column[species] if k]
        _, per_key = np.unique(np.array(keys, dtype=str), return_counts=True)
        eligible = int((per_key >= min_scope_species).sum())
        typer.echo(f"{label}: {len(per_key):,}; with ≥{min_scope_species} species: {eligible:,}")


@app.command("run")
def run_command(
    db: DbOption,
    lance_dir: Annotated[
        Path, typer.Option("--lance-dir", help="LanceDB database directory (biocosmos.lance).")
    ],
    lance_table: Annotated[str, typer.Option("--lance-table")] = "nymphalidae",
    image_table: ImageTableOption = "image_meta",
    taxonomy_table: TaxonomyTableOption = "image_meta_taxonomy",
    column: Annotated[str, typer.Option("--column")] = "unicom_embeddings",
    min_images: Annotated[int, typer.Option("--min-images")] = 3,
    min_scope_species: Annotated[int, typer.Option("--min-scope-species")] = 3,
    rarefy_k: Annotated[int, typer.Option("--rarefy-k")] = 5,
    bootstrap: Annotated[int, typer.Option("--bootstrap")] = 200,
    permutations: Annotated[int, typer.Option("--permutations")] = 999,
    permutation_max_species: Annotated[int, typer.Option("--permutation-max-species")] = 2000,
    mantel_max_species: Annotated[int, typer.Option("--max-mantel-species")] = 5000,
    batch_size: Annotated[int, typer.Option("--batch-size")] = 50_000,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    reports_dir: Annotated[Path | None, typer.Option("--reports-dir")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Compute the morphospaces into a run artifact. Reads both stores read-only."""
    try:
        parameters = MorphospaceParameters(
            embedding_column=column,
            min_images=min_images,
            min_scope_species=min_scope_species,
            rarefy_k=rarefy_k,
            bootstrap=bootstrap,
            permutations=permutations,
            permutation_max_species=permutation_max_species,
            mantel_max_species=mantel_max_species,
            batch_size=batch_size,
            seed=seed,
        )
        result = execute_run(
            database=db,
            lance_dir=lance_dir,
            lance_table=lance_table,
            parameters=parameters,
            reports_dir=_reports_dir(reports_dir),
            output=output,
            image_table=image_table,
            taxonomy_table=taxonomy_table,
            force=force,
        )
    except (HarmonizeError, ValueError, duckdb.Error) as exc:
        raise _fail(exc) from exc
    typer.echo(f"Created {result.database_path}")
    counts = result.counts
    typer.echo(
        f"Species: {counts['species']:,}; scopes: {counts['scopes_all']} all, "
        f"{counts['scopes_family']:,} families, {counts['scopes_genus']:,} genera"
    )
    typer.echo(f"Runtime: {format_duration(result.runtime_seconds)}")


def _resolve_run(run: str, reports_dir: Path | None) -> Path:
    """A run directory, from a path or from `latest` in the reports pointer file."""
    if run != "latest":
        return Path(run)
    root = _reports_dir(reports_dir)
    if root is None or not (root / LATEST_NAME).is_file():
        raise OutputError("No reports/latest.json; pass --run <run directory>.")
    pointer = json.loads((root / LATEST_NAME).read_text(encoding="utf-8"))
    entry = pointer.get(REPORT_KIND)
    if not isinstance(entry, dict) or "manifest" not in entry:
        raise OutputError(f"reports/latest.json has no {REPORT_KIND!r} run.")
    manifest = Path(entry["manifest"])
    return (manifest if manifest.is_absolute() else root / manifest).parent


@app.command("integrate")
def integrate_command(
    db: DbOption,
    run: Annotated[str, typer.Option("--run", help="Run directory, or 'latest'.")] = "latest",
    prefix: Annotated[str, typer.Option("--prefix")] = DEFAULT_PREFIX,
    reports_dir: Annotated[Path | None, typer.Option("--reports-dir")] = None,
    replace: Annotated[bool, typer.Option("--replace/--no-replace")] = False,
) -> None:
    """Copy a run's tables into the backend database.

    DuckDB allows a single writer: stop the backend first.
    """
    try:
        repository = MorphospaceOutputRepository(_resolve_run(run, reports_dir))
        report = repository.write_back(db, default_destinations(prefix), replace=replace)
    except (HarmonizeError, duckdb.Error) as exc:
        raise _fail(exc) from exc
    for table, rows in report.tables.items():
        typer.echo(f"Wrote {rows:,} rows to {table}")


if __name__ == "__main__":  # pragma: no cover
    app()
