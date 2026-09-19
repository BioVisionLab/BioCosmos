"""Command-line interface for geoharmonize."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any

import duckdb
import typer
from harmonize_core.errors import ConfigurationError, HarmonizeError
from harmonize_core.outputs import describe_artifact
from harmonize_core.progress import RunReporter, format_duration
from harmonize_core.reports import DEFAULT_REPORTS_DIR, run_directory, update_latest
from harmonize_core.sources import DuckDBCatalog

from geoharmonize import __version__
from geoharmonize.config import (
    load_project_config,
    merge_coordinate_config,
    parse_coordinate_mapping_options,
)
from geoharmonize.config import write_template as create_template
from geoharmonize.coordinates import CoordinateValidationPipeline
from geoharmonize.geography import GadmSource
from geoharmonize.models import (
    CoordinateColumnMappings,
    CoordinateRunManifest,
    CoordinateValidationConfig,
)
from geoharmonize.outputs import CoordinateOutputRepository
from geoharmonize.sources import CoordinateOccurrenceSource

REPORT_KIND = "geography"

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def _fail(exc: Exception) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=2) from exc


def _resolve_reports_dir(cli_value: Path | None, config_value: Path | None) -> Path | None:
    """Pick the reports root, preferring the CLI over the configuration file."""
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    return DEFAULT_REPORTS_DIR if DEFAULT_REPORTS_DIR.is_dir() else None


def _run_overrides(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


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
        _fail(exc)


@app.command("validate-coordinates")
def validate_coordinates_command(
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
    """Validate occurrence coordinates against a GADM ADM1 GeoPackage layer."""
    started = datetime.now(UTC)
    timer_started = perf_counter()
    progress = RunReporter(total_steps=9)
    run_id = str(uuid.uuid4())
    try:
        with progress.step("Validate configuration and coordinate columns"):
            project = load_project_config(config)
            reports_root = _resolve_reports_dir(
                reports_dir, project.coordinates.reports_dir or project.run.reports_dir
            )
            if output is None and reports_root is not None:
                output = run_directory(reports_root, REPORT_KIND, run_id)
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
            occurrence = CoordinateOccurrenceSource(effective.db, effective.table)
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
            points_per_second = distinct_points / runtime_seconds if runtime_seconds > 0 else None
            metadata_connection = duckdb.connect(str(repository.database_path))
            try:
                metadata_connection.execute(
                    "UPDATE coordinate_run_metadata SET completed_at = ?, runtime_seconds = ?",
                    [completed.isoformat(), runtime_seconds],
                )
            finally:
                metadata_connection.close()
            produced = {"database": repository.database_path}
            outputs = {role: str(path.resolve()) for role, path in produced.items()}
            outputs["manifest"] = str(repository.manifest_path.resolve())
            artifacts = [describe_artifact(role, path) for role, path in produced.items()]
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
                artifacts=artifacts,
                counts={
                    "total": total_rows,
                    "distinct_valid_points": distinct_points,
                    **{key.lower(): value for key, value in counts.items()},
                },
            )
            manifest_path = repository.write_manifest(manifest, force=effective.force)
            if reports_root is not None:
                update_latest(
                    reports_root,
                    REPORT_KIND,
                    run_id=run_id,
                    completed_at=completed.isoformat(),
                    manifest=manifest_path,
                )

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
    except (HarmonizeError, ValueError, duckdb.Error) as exc:
        _fail(exc)


if __name__ == "__main__":  # pragma: no cover
    app()
