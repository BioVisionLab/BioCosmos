"""Command-line interface for geoharmonize."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import duckdb
import typer
from harmonize_core.errors import ConfigurationError, HarmonizeError
from harmonize_core.progress import format_duration
from harmonize_core.sources import DuckDBCatalog

from geoharmonize.config import load_project_config, parse_coordinate_mapping_options
from geoharmonize.config import write_template as create_template
from geoharmonize.models import CoordinateColumnMappings
from geoharmonize.runs import CoordinateRunResult, execute_coordinate_run, run_overrides
from geoharmonize.sources import CoordinateOccurrenceSource

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"Error: {exc}", err=True)
    return typer.Exit(code=2)


def _echo_run_summary(result: CoordinateRunResult) -> None:
    """Report what the run found, in the same shape for both commands."""
    typer.echo(f"Created {result.database_path}")
    counts = result.counts
    mismatch_count = counts.get("COUNTRY_MISMATCH", 0) + counts.get("ADM1_MISMATCH", 0)
    unresolved_count = result.total_rows - counts.get("VALID", 0) - mismatch_count
    typer.echo(
        f"Occurrences: {result.total_rows:,}; valid: {counts.get('VALID', 0):,}; "
        f"mismatched: {mismatch_count:,}; invalid or unresolved: {unresolved_count:,}"
    )
    throughput = (
        result.distinct_points / result.runtime_seconds if result.runtime_seconds > 0 else 0.0
    )
    typer.echo(
        f"Runtime: {format_duration(result.runtime_seconds)} "
        f"({throughput:,.1f} distinct valid points/second)"
    )


@app.command("init")
def init_command(
    output: Annotated[str, typer.Option("--output", "-o")] = "harmonize.toml",
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Generate a commented TOML configuration template."""
    try:
        path = create_template(output, force=force)
        if path is not None:
            typer.echo(f"Created {path}")
    except HarmonizeError as exc:
        raise _fail(exc) from exc


@app.command("inspect")
def inspect_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    list_tables: Annotated[bool, typer.Option("--list-tables")] = False,
    list_columns: Annotated[str | None, typer.Option("--list-columns")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
) -> None:
    """List or inspect DuckDB tables without validating coordinates."""
    try:
        project = load_project_config(config)
        database = db or project.coordinates.db or project.run.db
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
        table_name = table or project.coordinates.table or project.run.table
        if table_name is None:
            raise ConfigurationError(
                "inspect requires --table, --list-tables, or --list-columns TABLE"
            )
        mapping_data = project.coordinate_columns.model_dump()
        mapping_data.update(parse_coordinate_mapping_options(mappings))
        report = CoordinateOccurrenceSource(database, table_name).inspect(
            CoordinateColumnMappings.model_validate(mapping_data)
        )
        typer.echo(f"Database: {report.database}")
        typer.echo(f"Table: {report.table}")
        typer.echo(f"Rows: {report.row_count:,}")
        typer.echo(f"Distinct coordinate pairs: {report.distinct_point_count:,}")
        typer.echo("Detected columns:")
        for logical, physical in sorted(report.detected_columns.items()):
            typer.echo(f"  {logical}: {physical}")
        for warning in report.warnings:
            typer.echo(f"Warning: {warning}")
        if not report.valid:
            raise typer.Exit(code=2)
    except (HarmonizeError, ValueError) as exc:
        raise _fail(exc) from exc


@app.command("validate")
def validate_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    gadm: Annotated[Path | None, typer.Option("--gadm")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    reports_dir: Annotated[Path | None, typer.Option("--reports-dir")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
    gadm_layer: Annotated[str | None, typer.Option("--gadm-layer")] = None,
    tile_size: Annotated[float | None, typer.Option("--tile-size")] = None,
    tile_buffer: Annotated[float | None, typer.Option("--tile-buffer")] = None,
    force: Annotated[bool | None, typer.Option("--force/--no-force")] = None,
) -> None:
    """Validate occurrence coordinates against a GADM ADM1 GeoPackage layer.

    Reads the occurrence database and never writes to it; use `integrate` to
    write the result back.
    """
    try:
        result = execute_coordinate_run(
            config=config,
            output=output,
            reports_dir=reports_dir,
            mappings=mappings,
            overrides=run_overrides(
                db=db,
                table=table,
                gadm=gadm,
                gadm_layer=gadm_layer,
                tile_size=tile_size,
                tile_buffer=tile_buffer,
                force=force,
            ),
        )
    except (HarmonizeError, ValueError, duckdb.Error) as exc:
        raise _fail(exc) from exc
    _echo_run_summary(result)


@app.command("integrate")
def integrate_command(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    table: Annotated[str | None, typer.Option("--table")] = None,
    gadm: Annotated[Path | None, typer.Option("--gadm")] = None,
    into: Annotated[str | None, typer.Option("--into", "--write-back-table")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    reports_dir: Annotated[Path | None, typer.Option("--reports-dir")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
    gadm_layer: Annotated[str | None, typer.Option("--gadm-layer")] = None,
    tile_size: Annotated[float | None, typer.Option("--tile-size")] = None,
    tile_buffer: Annotated[float | None, typer.Option("--tile-buffer")] = None,
    force: Annotated[bool | None, typer.Option("--force/--no-force")] = None,
    replace: Annotated[bool, typer.Option("--replace/--no-replace")] = False,
) -> None:
    """Validate coordinates and write the result into the occurrence database.

    Writes one row per occurrence, keyed on the mapped source id, so the result
    can be joined straight back to the table it was read from. DuckDB allows a
    single writer, so nothing else may hold the database open.
    """
    try:
        result = execute_coordinate_run(
            config=config,
            output=output,
            reports_dir=reports_dir,
            mappings=mappings,
            overrides=run_overrides(
                db=db,
                table=table,
                gadm=gadm,
                gadm_layer=gadm_layer,
                tile_size=tile_size,
                tile_buffer=tile_buffer,
                force=force,
                write_back_table=into,
            ),
            integrate=True,
            replace_existing=replace,
        )
    except (HarmonizeError, ValueError, duckdb.Error) as exc:
        raise _fail(exc) from exc
    _echo_run_summary(result)
    report = result.write_back
    assert report is not None
    typer.echo(f"Wrote {report.row_count:,} rows to {report.table}")
    if report.skipped_null_source_ids:
        typer.echo(
            f"Warning: {report.skipped_null_source_ids:,} rows had no source id and were skipped"
        )
    if report.distinct_source_ids != report.row_count:
        duplicates = report.row_count - report.distinct_source_ids
        typer.echo(
            f"Warning: {duplicates:,} duplicate source ids; joins on this table will fan out"
        )


if __name__ == "__main__":  # pragma: no cover
    app()
