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
    manifest = json.loads((output / "run.json").read_text())
    assert manifest["counts"]["total"] == 10
    assert manifest["outputs"]["manifest"].endswith("run.json")

    summary_result = runner.invoke(
        app,
        [
            "summarize",
            "--input",
            str(output / "taxonomy_update.duckdb"),
            "--csv",
            "--plot",
            "--force",
        ],
    )
    assert summary_result.exit_code == 0, summary_result.output


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
