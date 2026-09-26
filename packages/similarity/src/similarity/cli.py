"""Command-line interface for similarity."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from harmonize_core.errors import HarmonizeError, SourceValidationError
from harmonize_core.progress import format_duration

from similarity.compute import (
    batch_similarity_search,
    build_results,
    compute_centroids,
    normalize_species,
)
from similarity.outputs import summarize, write_results
from similarity.sources import load_all_embeddings, load_metadata, open_embeddings

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

DEFAULT_TOP_K = 800
DEFAULT_LIMIT = 10


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"Error: {exc}", err=True)
    return typer.Exit(code=2)


@app.callback()
def main() -> None:
    """Precompute the visually similar species the species pages show."""


@app.command("run")
def run_command(
    db: Annotated[Path, typer.Option("--db", help="Backend DuckDB file (biocosmos.duckdb).")],
    lance_dir: Annotated[
        Path, typer.Option("--lance-dir", help="LanceDB database directory (biocosmos.lance).")
    ],
    lance_table: Annotated[str, typer.Option("--lance-table")] = "nymphalidae",
    meta_table: Annotated[str, typer.Option("--meta-table")] = "image_meta",
    similarity_table: Annotated[str, typer.Option("--similarity-table")] = "species_similarity",
    top_k: Annotated[
        int, typer.Option("--top-k", min=1, help="Neighbors to fetch per centroid before dedup.")
    ] = DEFAULT_TOP_K,
    limit: Annotated[
        int, typer.Option("--limit", min=1, help="Final unique species per side.")
    ] = DEFAULT_LIMIT,
    species: Annotated[
        str | None, typer.Option("--species", help="Recompute a single species only.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Drop and recreate the similarity table.")
    ] = False,
) -> None:
    """Compute similar species and write them into the backend DuckDB.

    Stop the backend first: DuckDB allows a single writer.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    started = time.perf_counter()
    try:
        if not db.is_file():
            raise SourceValidationError(f"DuckDB file not found: {db}")
        embeddings, img_ids = load_all_embeddings(open_embeddings(lance_dir, lance_table))
        try:
            connection = duckdb.connect(str(db))
        except duckdb.Error as exc:
            raise SourceValidationError(
                f"Cannot open {db} for writing. Stop the backend first: DuckDB allows a "
                "single writer, and a second process cannot attach while it holds the file."
            ) from exc
        try:
            meta = load_metadata(connection, meta_table)
            species_filter = normalize_species(species) if species else None
            keys, centroids = compute_centroids(meta, embeddings, img_ids, species_filter)
            if not keys:
                typer.echo("No species × side groups found; nothing written.")
                return
            top_indices, top_distances = batch_similarity_search(centroids, embeddings, top_k)
            results = build_results(keys, top_indices, top_distances, img_ids, meta, limit)
            write_results(
                connection, similarity_table, results, species=species_filter, force=force
            )
            counts = summarize(connection, similarity_table)
        finally:
            connection.close()
    except (HarmonizeError, duckdb.Error) as exc:
        raise _fail(exc) from exc
    typer.echo(f"Wrote {similarity_table} in {format_duration(time.perf_counter() - started)}")
    for name, count in counts.items():
        typer.echo(f"  {name}: {count:,}")
