"""One coordinate-validation run, shared by the `validate` and `integrate` commands.

The two commands differ only at the ends: `integrate` additionally writes the
result into the occurrence database, and each prints its own summary. The run
itself — configuration, GADM validation, the pipeline, the manifest — is the
same, and lives here so neither command owns a copy of it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
from harmonize_core.errors import ConfigurationError
from harmonize_core.identifiers import parse_table_identifier
from harmonize_core.outputs import describe_artifact
from harmonize_core.progress import RunReporter
from harmonize_core.reports import DEFAULT_REPORTS_DIR, run_directory, update_latest

from geoharmonize import __version__
from geoharmonize.config import load_project_config, merge_coordinate_config
from geoharmonize.coordinates import CoordinateValidationPipeline
from geoharmonize.geography import GadmSource
from geoharmonize.models import (
    CoordinateRunManifest,
    CoordinateValidationConfig,
    EffectiveCoordinateRunConfig,
    WriteBackReport,
)
from geoharmonize.outputs import CoordinateOutputRepository
from geoharmonize.sources import CoordinateOccurrenceSource

REPORT_KIND = "geography"

# `validate` reports nine stages; `integrate` adds the write-back.
VALIDATE_STEPS = 9
INTEGRATE_STEPS = 10


@dataclass(frozen=True)
class CoordinateRunResult:
    """What one run produced, for the command to report on."""

    run_id: str
    effective: EffectiveCoordinateRunConfig
    database_path: Path
    manifest_path: Path
    counts: dict[str, int]
    total_rows: int
    distinct_points: int
    runtime_seconds: float
    write_back: WriteBackReport | None = None


def resolve_reports_dir(cli_value: Path | None, config_value: Path | None) -> Path | None:
    """Pick the reports root, preferring the CLI over the configuration file."""
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    return DEFAULT_REPORTS_DIR if DEFAULT_REPORTS_DIR.is_dir() else None


def run_overrides(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def execute_coordinate_run(
    *,
    config: Path | None,
    output: Path | None,
    reports_dir: Path | None,
    mappings: list[str] | None,
    overrides: dict[str, Any],
    integrate: bool = False,
    replace_existing: bool = False,
) -> CoordinateRunResult:
    """Validate coordinates, and optionally write the result back.

    Raises `HarmonizeError`, `ValueError` or `duckdb.Error`; the commands turn
    those into an exit code.
    """
    started = datetime.now(UTC)
    timer_started = perf_counter()
    progress = RunReporter(total_steps=INTEGRATE_STEPS if integrate else VALIDATE_STEPS)
    run_id = str(uuid.uuid4())

    with progress.step("Validate configuration and coordinate columns"):
        project = load_project_config(config)
        reports_root = resolve_reports_dir(
            reports_dir, project.coordinates.reports_dir or project.run.reports_dir
        )
        if output is None and reports_root is not None:
            output = run_directory(reports_root, REPORT_KIND, run_id)
        effective = merge_coordinate_config(
            project,
            overrides={**overrides, **run_overrides(output=output)},
            mapping_values=mappings,
        )
        occurrence = CoordinateOccurrenceSource(effective.db, effective.table)
        with occurrence.connect() as source_connection:
            available = occurrence.columns(source_connection)
            resolved, _ = occurrence.resolve_coordinate_columns(
                available, effective.columns, strict=True
            )
        if integrate:
            _check_integration_preconditions(effective, occurrence, resolved)
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

    # The occurrence database is attached read-only for the duration of the
    # block above, and DuckDB allows a single writer -- so the write-back can
    # only open it once `build_database` has closed its connection.
    write_back: WriteBackReport | None = None
    if integrate:
        assert effective.write_back_table is not None
        with progress.step("Write validated coordinates into the occurrence database"):
            write_back = repository.write_back(
                effective.db,
                effective.write_back_table,
                replace=replace_existing,
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
        if write_back is not None:
            outputs["write_back_table"] = write_back.table
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

    return CoordinateRunResult(
        run_id=run_id,
        effective=effective,
        database_path=repository.database_path,
        manifest_path=manifest_path,
        counts=counts,
        total_rows=total_rows,
        distinct_points=distinct_points,
        runtime_seconds=perf_counter() - timer_started,
        write_back=write_back,
    )


def _check_integration_preconditions(
    effective: EffectiveCoordinateRunConfig,
    occurrence: CoordinateOccurrenceSource,
    resolved: dict[str, str],
) -> None:
    """Refuse an integration that could not produce a usable table.

    Checked before any work, because each of these only becomes visible after
    the run has already cost minutes.
    """
    if effective.write_back_table is None:
        raise ConfigurationError(
            "integrate requires --into, directly or as write_back_table in TOML"
        )
    if "source_id" not in resolved:
        raise ConfigurationError(
            "integrate requires a source_id column to key the written table; "
            "map it with --map source_id=COLUMN"
        )
    destination = parse_table_identifier(effective.write_back_table)
    if destination == occurrence.identifier:
        raise ConfigurationError(
            f"--into names the table being read: {destination.display_name}. "
            "Write the result to a different table."
        )
