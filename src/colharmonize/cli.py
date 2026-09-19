"""Command-line interface for colharmonize."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any

import duckdb
import typer

from colharmonize import __version__
from colharmonize.config import (
    load_project_config,
    merge_coordinate_config,
    merge_run_config,
    parse_mapping_options,
)
from colharmonize.config import write_template as create_template
from colharmonize.coordinates import CoordinateValidationPipeline
from colharmonize.errors import ColHarmonizeError, ConfigurationError
from colharmonize.geography import GadmSource
from colharmonize.index import ReferenceIndex
from colharmonize.models import (
    ColumnMappings,
    CoordinateRunManifest,
    CoordinateValidationConfig,
    RunManifest,
)
from colharmonize.outputs import CoordinateOutputRepository, OutputRepository
from colharmonize.pipeline import MatchPipeline
from colharmonize.progress import RunReporter, format_duration
from colharmonize.sources import ColSource, DuckDBCatalog, OccurrenceSource
from colharmonize.summary import SummaryService, resolve_palette_name

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def _fail(exc: Exception) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=2) from exc


@app.command("init")
def init_command(
    output: Annotated[str, typer.Option("--output", "-o")] = "colharmonize.toml",
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Generate a commented TOML configuration template."""
    try:
        path = create_template(output, force=force)
        if path is not None:
            typer.echo(f"Created {path}")
    except ColHarmonizeError as exc:
        _fail(exc)


@app.command("inspect")
def inspect_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    list_tables: Annotated[bool, typer.Option("--list-tables")] = False,
    list_columns: Annotated[str | None, typer.Option("--list-columns")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
) -> None:
    """List or inspect DuckDB tables without performing matching."""
    try:
        project = load_project_config(config)
        database = db or project.run.db
        if database is None:
            raise ConfigurationError("inspect requires --db, directly or in TOML")
        if list_tables or list_columns is not None:
            catalog = DuckDBCatalog(database)
            if list_tables:
                tables = catalog.list_tables()
                typer.echo("Schema\tTable\tType")
                for item in tables:
                    typer.echo(f"{item.schema_name}\t{item.table_name}\t{item.table_type}")
            if list_columns is not None:
                columns = catalog.list_columns(list_columns)
                typer.echo(f"Columns in {list_columns}:")
                typer.echo("Name\tType\tNullable")
                for column in columns:
                    nullable = "YES" if column.nullable else "NO"
                    typer.echo(f"{column.name}\t{column.data_type}\t{nullable}")
            return
        table_name = table or project.run.table
        if table_name is None:
            raise ConfigurationError(
                "inspect requires --table, --list-tables, or --list-columns TABLE"
            )
        mapping_data = project.columns.model_dump(by_alias=True)
        mapping_data.update(parse_mapping_options(mappings))
        report = OccurrenceSource(database, table_name).inspect(
            ColumnMappings.model_validate(mapping_data)
        )
        typer.echo(f"Database: {report.database}")
        typer.echo(f"Table: {report.table}")
        typer.echo(f"Rows: {report.row_count:,}")
        typer.echo(f"Distinct taxonomic combinations: {report.distinct_taxon_count:,}")
        typer.echo("Detected columns:")
        for logical, physical in sorted(report.detected_columns.items()):
            typer.echo(f"  {logical}: {physical}")
        for warning in report.warnings:
            typer.echo(f"Warning: {warning}")
        if not report.valid:
            raise typer.Exit(code=2)
    except (ColHarmonizeError, ValueError) as exc:
        _fail(exc)


@app.command("index")
def index_command(
    col: Annotated[Path | None, typer.Option("--col")] = None,
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    rebuild: Annotated[bool, typer.Option("--rebuild")] = False,
) -> None:
    """Create or reuse a local Catalogue of Life index."""
    try:
        project = load_project_config(config)
        source_path = col or project.run.col
        if source_path is None:
            raise ConfigurationError("index requires --col, directly or in TOML")
        cache = cache_dir or project.run.cache_dir or Path.home() / ".cache" / "colharmonize"
        info = ReferenceIndex(cache).ensure(ColSource(source_path), rebuild=rebuild)
        action = "Reused" if info.reused else "Created"
        typer.echo(f"{action} {info.path}")
        typer.echo(f"Accepted taxa: {info.accepted_count:,}; name usages: {info.usage_count:,}")
    except (ColHarmonizeError, ValueError) as exc:
        _fail(exc)


def _run_overrides(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


@app.command("run")
def run_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    col: Annotated[Path | None, typer.Option("--col")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
    top_k: Annotated[int | None, typer.Option("--top-k")] = None,
    short_epithet_length: Annotated[int | None, typer.Option()] = None,
    short_epithet_distance: Annotated[int | None, typer.Option()] = None,
    long_epithet_distance: Annotated[int | None, typer.Option()] = None,
    genus_distance: Annotated[int | None, typer.Option()] = None,
    min_genus_similarity: Annotated[float | None, typer.Option()] = None,
    min_score_margin: Annotated[int | None, typer.Option()] = None,
    csv: Annotated[bool | None, typer.Option("--csv/--no-csv")] = None,
    plot: Annotated[bool | None, typer.Option("--plot/--no-plot")] = None,
    plot_palette: Annotated[str | None, typer.Option("--plot-palette")] = None,
    force: Annotated[bool | None, typer.Option("--force/--no-force")] = None,
    write_back_table: Annotated[str | None, typer.Option("--write-back-table")] = None,
) -> None:
    """Match distinct occurrence taxa against a Catalogue of Life release."""
    started = datetime.now(UTC)
    timer_started = perf_counter()
    progress = RunReporter(total_steps=10)
    try:
        with progress.step("Validate configuration and input columns"):
            project = load_project_config(config)
            effective = merge_run_config(
                project,
                overrides=_run_overrides(
                    db=db,
                    table=table,
                    col=col,
                    output=output,
                    cache_dir=cache_dir,
                    top_k=top_k,
                    short_epithet_length=short_epithet_length,
                    short_epithet_distance=short_epithet_distance,
                    long_epithet_distance=long_epithet_distance,
                    genus_distance=genus_distance,
                    min_genus_similarity=min_genus_similarity,
                    min_score_margin=min_score_margin,
                    csv=csv,
                    plot=plot,
                    plot_palette=plot_palette,
                    force=force,
                    write_back_table=write_back_table,
                ),
                mapping_values=mappings,
            )
            resolved_plot_palette = (
                resolve_palette_name(effective.plot_palette)
                if effective.plot
                else effective.plot_palette
            )
            occurrence = OccurrenceSource(effective.db, effective.table)
            with occurrence.connect() as source_connection:
                available = occurrence.columns(source_connection)
                resolved, _ = occurrence.resolve_columns(available, effective.columns, strict=True)

        with progress.step("Prepare the Catalogue of Life reference index"):
            index_info = ReferenceIndex(effective.cache_dir).ensure(ColSource(effective.col))
        repository = OutputRepository(effective.output)
        run_id = str(uuid.uuid4())
        with repository.build_database(force=effective.force) as connection:
            MatchPipeline(
                connection,
                occurrence,
                resolved,
                index_info.path,
                effective.matching,
            ).run(stage=progress.step)
            with progress.step("Calculate summary metrics"):
                SummaryService().refresh_metrics(connection)
                counts = dict(
                    connection.execute(
                        "SELECT update_status, count(*) "
                        "FROM taxonomy_matches GROUP BY update_status"
                    ).fetchall()
                )
                connection.execute(
                    """
                    CREATE TABLE run_metadata AS SELECT
                        ?::VARCHAR AS run_id,
                        ?::VARCHAR AS package_version,
                        ?::TIMESTAMPTZ AS started_at,
                        NULL::TIMESTAMPTZ AS completed_at,
                        NULL::DOUBLE AS runtime_seconds,
                        ?::VARCHAR AS occurrence_database,
                        ?::VARCHAR AS occurrence_table,
                        ?::VARCHAR AS col_source,
                        ?::VARCHAR AS col_sha256,
                        ?::VARCHAR AS reference_index,
                        ?::JSON AS detected_columns,
                        ?::JSON AS matching_config,
                        ?::BIGINT AS input_taxon_count,
                        ?::BIGINT AS matched_count,
                        ?::BIGINT AS ambiguous_count,
                        ?::BIGINT AS unmatched_count
                    """,
                    [
                        run_id,
                        __version__,
                        started.isoformat(),
                        str(effective.db.resolve()),
                        occurrence.identifier.display_name,
                        str(effective.col.resolve()),
                        index_info.fingerprint,
                        str(index_info.path.resolve()),
                        json.dumps(resolved, sort_keys=True),
                        json.dumps(effective.matching.model_dump(), sort_keys=True),
                        sum(counts.values()),
                        counts.get("MATCHED", 0),
                        counts.get("AMBIGUOUS", 0),
                        counts.get("UNMATCHED", 0),
                    ],
                )

        with progress.step("Export requested artifacts"):
            summary = SummaryService()
            outputs = {"database": str(repository.database_path.resolve())}
            if effective.csv:
                outputs["csv"] = str(
                    summary.export_csv(
                        repository.database_path, effective.output, force=effective.force
                    ).resolve()
                )
            if effective.plot:
                outputs["plot"] = str(
                    summary.export_plot(
                        repository.database_path,
                        effective.output,
                        force=effective.force,
                        palette=resolved_plot_palette,
                    ).resolve()
                )
            if effective.write_back_table:
                repository.write_back(effective.db, effective.write_back_table)
                outputs["write_back_table"] = effective.write_back_table
            outputs["manifest"] = str((effective.output / "run.json").resolve())

        total = sum(counts.values())
        with progress.step("Finalize run metadata"):
            completed = datetime.now(UTC)
            runtime_seconds = perf_counter() - timer_started
            taxa_per_second = total / runtime_seconds if runtime_seconds > 0 else None
            metadata_connection = duckdb.connect(str(repository.database_path))
            try:
                metadata_connection.execute(
                    "UPDATE run_metadata SET completed_at = ?, runtime_seconds = ?",
                    [completed.isoformat(), runtime_seconds],
                )
            finally:
                metadata_connection.close()
            manifest = RunManifest(
                run_id=run_id,
                package_version=__version__,
                started_at=started.isoformat(),
                completed_at=completed.isoformat(),
                runtime_seconds=round(runtime_seconds, 3),
                taxa_per_second=(
                    round(taxa_per_second, 3) if taxa_per_second is not None else None
                ),
                occurrence_database=str(effective.db.resolve()),
                occurrence_table=occurrence.identifier.display_name,
                col_source=str(effective.col.resolve()),
                col_sha256=index_info.fingerprint,
                reference_index=str(index_info.path.resolve()),
                detected_columns=resolved,
                matching=effective.matching.model_dump(),
                outputs=outputs,
                counts={"total": total, **{key.lower(): value for key, value in counts.items()}},
            )
            repository.write_manifest(manifest, force=effective.force)
        typer.echo(f"Created {repository.database_path}")
        typer.echo(
            f"Input taxa: {total:,}; matched: {counts.get('MATCHED', 0):,}; "
            f"ambiguous: {counts.get('AMBIGUOUS', 0):,}; "
            f"unmatched: {counts.get('UNMATCHED', 0):,}"
        )
        final_runtime = perf_counter() - timer_started
        throughput = total / final_runtime if final_runtime > 0 else 0.0
        typer.echo(
            f"Runtime: {format_duration(final_runtime)} ({throughput:,.1f} distinct taxa/second)"
        )
    except (ColHarmonizeError, ValueError, duckdb.Error) as exc:
        _fail(exc)


@app.command("validate-coordinates")
def validate_coordinates_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    gadm: Annotated[Path | None, typer.Option("--gadm")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
    gadm_layer: Annotated[str | None, typer.Option("--gadm-layer")] = None,
    tile_size: Annotated[float | None, typer.Option("--tile-size")] = None,
    tile_buffer: Annotated[float | None, typer.Option("--tile-buffer")] = None,
    force: Annotated[bool | None, typer.Option("--force/--no-force")] = None,
) -> None:
    """Validate occurrence coordinates against a GADM ADM1 GeoPackage layer."""
    started = datetime.now(UTC)
    timer_started = perf_counter()
    progress = RunReporter(total_steps=9)
    try:
        with progress.step("Validate configuration and coordinate columns"):
            project = load_project_config(config)
            effective = merge_coordinate_config(
                project,
                overrides=_run_overrides(
                    db=db,
                    table=table,
                    gadm=gadm,
                    output=output,
                    gadm_layer=gadm_layer,
                    tile_size=tile_size,
                    tile_buffer=tile_buffer,
                    force=force,
                ),
                mapping_values=mappings,
            )
            occurrence = OccurrenceSource(effective.db, effective.table)
            with occurrence.connect() as source_connection:
                available = occurrence.columns(source_connection)
                resolved, _ = occurrence.resolve_coordinate_columns(
                    available, effective.columns, strict=True
                )
            validation_config = CoordinateValidationConfig(
                tile_size=effective.tile_size,
                tile_buffer=effective.tile_buffer,
            )

        with progress.step("Validate the GADM reference layer"):
            gadm_source = GadmSource(effective.gadm)
            gadm_info = gadm_source.inspect(effective.gadm_layer)

        repository = CoordinateOutputRepository(effective.output)
        run_id = str(uuid.uuid4())
        with repository.build_database(force=effective.force) as connection:
            pipeline = CoordinateValidationPipeline(
                connection,
                occurrence,
                resolved,
                gadm_source,
                gadm_info,
                validation_config,
            )
            pipeline.run(stage=progress.step)
            with progress.step("Calculate coordinate summary and provenance"):
                pipeline.refresh_metrics()
                counts = dict(
                    connection.execute(
                        "SELECT validation_status, count(*) "
                        "FROM coordinate_validation GROUP BY validation_status"
                    ).fetchall()
                )
                total_rows = sum(counts.values())
                point_count_row = connection.execute(
                    "SELECT count(*) FROM coordinate_points"
                ).fetchone()
                assert point_count_row is not None
                distinct_points = point_count_row[0]
                connection.execute(
                    """
                    CREATE TABLE coordinate_run_metadata AS SELECT
                        ?::VARCHAR AS run_id,
                        ?::VARCHAR AS package_version,
                        ?::TIMESTAMPTZ AS started_at,
                        NULL::TIMESTAMPTZ AS completed_at,
                        NULL::DOUBLE AS runtime_seconds,
                        ?::VARCHAR AS occurrence_database,
                        ?::VARCHAR AS occurrence_table,
                        ?::VARCHAR AS gadm_source,
                        ?::VARCHAR AS gadm_sha256,
                        ?::VARCHAR AS gadm_layer,
                        ?::INTEGER AS gadm_srs_id,
                        ?::JSON AS detected_columns,
                        ?::JSON AS validation_config,
                        ?::BIGINT AS occurrence_count,
                        ?::BIGINT AS distinct_valid_point_count
                    """,
                    [
                        run_id,
                        __version__,
                        started.isoformat(),
                        str(effective.db.resolve()),
                        occurrence.identifier.display_name,
                        str(effective.gadm.resolve()),
                        gadm_info.fingerprint,
                        gadm_info.layer,
                        gadm_info.srs_id,
                        json.dumps(resolved, sort_keys=True),
                        json.dumps(validation_config.model_dump(), sort_keys=True),
                        total_rows,
                        distinct_points,
                    ],
                )

        with progress.step("Finalize coordinate run metadata"):
            completed = datetime.now(UTC)
            runtime_seconds = perf_counter() - timer_started
            points_per_second = (
                distinct_points / runtime_seconds if runtime_seconds > 0 else None
            )
            metadata_connection = duckdb.connect(str(repository.database_path))
            try:
                metadata_connection.execute(
                    "UPDATE coordinate_run_metadata SET completed_at = ?, runtime_seconds = ?",
                    [completed.isoformat(), runtime_seconds],
                )
            finally:
                metadata_connection.close()
            outputs = {
                "database": str(repository.database_path.resolve()),
                "manifest": str((effective.output / "coordinate_run.json").resolve()),
            }
            manifest = CoordinateRunManifest(
                run_id=run_id,
                package_version=__version__,
                started_at=started.isoformat(),
                completed_at=completed.isoformat(),
                runtime_seconds=round(runtime_seconds, 3),
                points_per_second=(
                    round(points_per_second, 3) if points_per_second is not None else None
                ),
                occurrence_database=str(effective.db.resolve()),
                occurrence_table=occurrence.identifier.display_name,
                gadm_source=str(effective.gadm.resolve()),
                gadm_sha256=gadm_info.fingerprint,
                gadm_layer=gadm_info.layer,
                detected_columns=resolved,
                validation=validation_config.model_dump(),
                outputs=outputs,
                counts={
                    "total": total_rows,
                    "distinct_valid_points": distinct_points,
                    **{key.lower(): value for key, value in counts.items()},
                },
            )
            repository.write_manifest(manifest, force=effective.force)

        typer.echo(f"Created {repository.database_path}")
        mismatch_count = counts.get("COUNTRY_MISMATCH", 0) + counts.get("ADM1_MISMATCH", 0)
        unresolved_count = total_rows - counts.get("VALID", 0) - mismatch_count
        typer.echo(
            f"Occurrences: {total_rows:,}; valid: {counts.get('VALID', 0):,}; "
            f"mismatched: {mismatch_count:,}; invalid or unresolved: {unresolved_count:,}"
        )
        final_runtime = perf_counter() - timer_started
        throughput = distinct_points / final_runtime if final_runtime > 0 else 0.0
        typer.echo(
            f"Runtime: {format_duration(final_runtime)} "
            f"({throughput:,.1f} distinct valid points/second)"
        )
    except (ColHarmonizeError, ValueError, duckdb.Error) as exc:
        _fail(exc)


@app.command("summarize")
def summarize_command(
    input_database: Annotated[Path, typer.Option("--input")],
    csv: Annotated[bool, typer.Option("--csv")] = False,
    plot: Annotated[bool, typer.Option("--plot")] = False,
    plot_palette: Annotated[str, typer.Option("--plot-palette")] = "Dark2",
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Regenerate metrics and optional artifacts from a completed run."""
    try:
        if not input_database.is_file():
            raise ConfigurationError(f"Output database does not exist: {input_database}")
        resolved_plot_palette = resolve_palette_name(plot_palette) if plot else plot_palette
        service = SummaryService()
        connection = duckdb.connect(str(input_database))
        try:
            service.refresh_metrics(connection)
        finally:
            connection.close()
        output_dir = input_database.parent
        if csv:
            service.export_csv(input_database, output_dir, force=force)
        if plot:
            service.export_plot(
                input_database, output_dir, force=force, palette=resolved_plot_palette
            )
        typer.echo(f"Summarized {input_database}")
    except (ColHarmonizeError, ValueError, duckdb.Error) as exc:
        _fail(exc)


if __name__ == "__main__":  # pragma: no cover
    app()
