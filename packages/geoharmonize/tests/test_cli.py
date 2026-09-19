from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from geoharmonize.cli import app

runner = CliRunner()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_init_writes_template(tmp_path: Path) -> None:
    destination = tmp_path / "harmonize.toml"
    result = runner.invoke(app, ["init", "--output", str(destination)])
    assert result.exit_code == 0
    assert "[coordinates]" in destination.read_text(encoding="utf-8")


def test_validate_coordinates_outputs_and_preserves_sources(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    occurrence_before = _sha256(coordinate_db)
    gadm_before = _sha256(gadm_gpkg)
    output = tmp_path / "coordinate-result"
    result = runner.invoke(
        app,
        [
            "validate-coordinates",
            "--db",
            str(coordinate_db),
            "--table",
            "main.occurrence",
            "--gadm",
            str(gadm_gpkg),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert occurrence_before == _sha256(coordinate_db)
    assert gadm_before == _sha256(gadm_gpkg)
    assert (output / "coordinate_validation.duckdb").is_file()
    assert (output / "coordinate_run.json").is_file()
    assert "[1/9] Validate configuration and coordinate columns" in result.output
    assert "[9/9] Finalize coordinate run metadata" in result.output
    assert "distinct valid points/second" in result.output

    manifest = json.loads((output / "coordinate_run.json").read_text())
    assert manifest["counts"]["total"] == 12
    assert manifest["counts"]["distinct_valid_points"] == 3
    assert manifest["gadm_layer"] == "ADM_ADM_1"

    connection = duckdb.connect(str(output / "coordinate_validation.duckdb"), read_only=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        runtime = connection.execute(
            "SELECT runtime_seconds FROM coordinate_run_metadata"
        ).fetchone()[0]
    finally:
        connection.close()
    assert {
        "coordinate_input_rows",
        "coordinate_points",
        "coordinate_reference_subset",
        "coordinate_reference_candidates",
        "coordinate_point_matches",
        "coordinate_validation",
        "coordinate_summary_metrics",
        "coordinate_run_metadata",
    } <= tables
    assert runtime > 0
