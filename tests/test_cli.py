from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from colharmonize.cli import app

runner = CliRunner()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_init_writes_template(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    result = runner.invoke(app, ["init", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert "[matching]" in target.read_text()


def test_inspect_catalog_options(occurrence_db: Path) -> None:
    tables = runner.invoke(app, ["inspect", "--db", str(occurrence_db), "--list-tables"])
    assert tables.exit_code == 0, tables.output
    assert "main\toccurrence\tBASE TABLE" in tables.output

    columns = runner.invoke(
        app,
        [
            "inspect",
            "--db",
            str(occurrence_db),
            "--list-columns",
            "main.occurrence",
        ],
    )
    assert columns.exit_code == 0, columns.output
    assert "scientificName\tVARCHAR" in columns.output


def test_run_outputs_and_preserves_source(
    occurrence_db: Path, col_tsv: Path, tmp_path: Path
) -> None:
    before = _sha256(occurrence_db)
    output = tmp_path / "result"
    result = runner.invoke(
        app,
        [
            "run",
            "--db",
            str(occurrence_db),
            "--table",
            "main.occurrence",
            "--map",
            "scientific_name=species",
            "--col",
            str(col_tsv),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output",
            str(output),
            "--csv",
            "--plot",
        ],
    )
    assert result.exit_code == 0, result.output
    assert before == _sha256(occurrence_db)
    assert (output / "taxonomy_update.duckdb").is_file()
    assert (output / "taxonomy_summary.csv").is_file()
    assert (output / "taxonomy_match_summary.png").is_file()
    assert (output / "run.json").is_file()
    assert "[1/10] Validate configuration and input columns" in result.output
    assert "[10/10] Finalize run metadata" in result.output
    assert "Runtime:" in result.output
    assert "distinct taxa/second" in result.output
    manifest = json.loads((output / "run.json").read_text())
    assert manifest["counts"]["total"] == 10
    assert manifest["runtime_seconds"] > 0
    assert manifest["taxa_per_second"] > 0
    assert manifest["outputs"]["manifest"].endswith("run.json")

    connection = duckdb.connect(str(output / "taxonomy_update.duckdb"), read_only=True)
    try:
        runtime_seconds = connection.execute("SELECT runtime_seconds FROM run_metadata").fetchone()[
            0
        ]
    finally:
        connection.close()
    assert runtime_seconds > 0

    summary_result = runner.invoke(
        app,
        [
            "summarize",
            "--input",
            str(output / "taxonomy_update.duckdb"),
            "--csv",
            "--plot",
            "--plot-palette",
            "dark2",
            "--force",
        ],
    )
    assert summary_result.exit_code == 0, summary_result.output


def test_invalid_plot_palette_fails_before_creating_output(
    occurrence_db: Path, col_tsv: Path, tmp_path: Path
) -> None:
    output = tmp_path / "invalid-palette"
    result = runner.invoke(
        app,
        [
            "run",
            "--db",
            str(occurrence_db),
            "--table",
            "main.occurrence",
            "--map",
            "scientific_name=species",
            "--col",
            str(col_tsv),
            "--output",
            str(output),
            "--plot",
            "--plot-palette",
            "not-a-real-palette",
        ],
    )
    assert result.exit_code == 2
    assert "Unknown Seaborn palette" in result.output
    assert not output.exists()


def test_opt_in_write_back_is_compact(occurrence_db: Path, col_tsv: Path, tmp_path: Path) -> None:
    output = tmp_path / "writeback"
    result = runner.invoke(
        app,
        [
            "run",
            "--db",
            str(occurrence_db),
            "--table",
            "occurrence",
            "--map",
            "scientific_name=species",
            "--col",
            str(col_tsv),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output",
            str(output),
            "--write-back-table",
            "harmonized.taxonomy_lookup",
        ],
    )
    assert result.exit_code == 0, result.output
    connection = duckdb.connect(str(occurrence_db), read_only=True)
    try:
        source_count = connection.execute("SELECT count(*) FROM occurrence").fetchone()[0]
        lookup_count = connection.execute(
            "SELECT count(*) FROM harmonized.taxonomy_lookup"
        ).fetchone()[0]
    finally:
        connection.close()
    assert source_count == 11
    assert lookup_count <= source_count

    second = runner.invoke(
        app,
        [
            "run",
            "--db",
            str(occurrence_db),
            "--table",
            "occurrence",
            "--map",
            "scientific_name=species",
            "--col",
            str(col_tsv),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output",
            str(tmp_path / "second-writeback"),
            "--write-back-table",
            "harmonized.taxonomy_lookup",
        ],
    )
    assert second.exit_code == 2
    connection = duckdb.connect(str(occurrence_db), read_only=True)
    try:
        assert (
            connection.execute("SELECT count(*) FROM harmonized.taxonomy_lookup").fetchone()[0]
            == lookup_count
        )
    finally:
        connection.close()


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
