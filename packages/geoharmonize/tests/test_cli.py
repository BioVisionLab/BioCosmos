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


def test_validate_outputs_and_preserves_sources(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    occurrence_before = _sha256(coordinate_db)
    gadm_before = _sha256(gadm_gpkg)
    output = tmp_path / "coordinate-result"
    result = runner.invoke(
        app,
        [
            "validate",
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
    assert manifest["counts"]["total"] == 13
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


def test_old_validate_command_name_is_gone() -> None:
    """The rename is hard: nothing keeps `validate-coordinates` working."""
    result = runner.invoke(app, ["validate-coordinates", "--help"])
    assert result.exit_code == 2


def _integrate(
    coordinate_db: Path,
    gadm_gpkg: Path,
    output: Path,
    *,
    table: str = "main.occurrence",
    into: str = "geo.image_meta_coordinates",
    extra: list[str] | None = None,
):
    return runner.invoke(
        app,
        [
            "integrate",
            "--db",
            str(coordinate_db),
            "--table",
            table,
            "--gadm",
            str(gadm_gpkg),
            "--output",
            str(output),
            "--into",
            into,
            *(extra or []),
        ],
    )


def test_integrate_writes_one_row_per_occurrence(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    """The written table is keyed on source_id and joinable back to the source.

    A qualified destination is used deliberately, so the run has to create the
    schema rather than finding one.
    """
    gadm_before = _sha256(gadm_gpkg)
    output = tmp_path / "integrate-result"
    result = _integrate(coordinate_db, gadm_gpkg, output)
    assert result.exit_code == 0, result.output
    assert gadm_before == _sha256(gadm_gpkg)
    assert "[10/10] Finalize coordinate run metadata" in result.output
    assert "Wrote 13 rows to geo.image_meta_coordinates" in result.output

    manifest = json.loads((output / "coordinate_run.json").read_text())
    assert manifest["outputs"]["write_back_table"] == "geo.image_meta_coordinates"

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        total, distinct = connection.execute(
            "SELECT count(*), count(DISTINCT source_id) FROM geo.image_meta_coordinates"
        ).fetchone()
        # The source table is read, never rewritten.
        assert connection.execute("SELECT count(*) FROM main.occurrence").fetchone()[0] == 13
        statuses = dict(
            connection.execute(
                "SELECT source_id, validation_status FROM geo.image_meta_coordinates"
            ).fetchall()
        )
        reference = dict(
            connection.execute(
                "SELECT source_id, reference_country FROM geo.image_meta_coordinates"
            ).fetchall()
        )
        run_id, gadm_sha = connection.execute(
            "SELECT DISTINCT run_id, gadm_sha256 FROM geo.image_meta_coordinates"
        ).fetchone()
    finally:
        connection.close()

    assert total == 13
    assert distinct == 13
    assert statuses["valid-code"] == "VALID"
    assert statuses["country-mismatch"] == "COUNTRY_MISMATCH"
    assert statuses["adm1-mismatch"] == "ADM1_MISMATCH"
    assert statuses["missing"] == "MISSING_COORDINATE"
    assert statuses["zero"] == "ZERO_COORDINATE"
    assert statuses["no-reference"] == "NO_REFERENCE_MATCH"
    assert statuses["ambiguous"] == "AMBIGUOUS_REFERENCE"
    # Reference columns are only populated when exactly one region matched.
    assert reference["valid-code"] == "United States"
    assert reference["ambiguous"] is None
    # Provenance travels on the row, so a reader needs no second table.
    assert run_id == manifest["run_id"]
    assert gadm_sha == manifest["gadm_sha256"]


def test_integrate_refuses_an_existing_destination(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    first = _integrate(coordinate_db, gadm_gpkg, tmp_path / "one")
    assert first.exit_code == 0, first.output
    original = json.loads((tmp_path / "one" / "coordinate_run.json").read_text())["run_id"]

    second = _integrate(coordinate_db, gadm_gpkg, tmp_path / "two")
    assert second.exit_code == 2
    assert "--replace" in second.output

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        kept = connection.execute(
            "SELECT DISTINCT run_id FROM geo.image_meta_coordinates"
        ).fetchone()[0]
    finally:
        connection.close()
    assert kept == original


def test_integrate_replaces_with_the_flag(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    first = _integrate(coordinate_db, gadm_gpkg, tmp_path / "one")
    assert first.exit_code == 0, first.output
    original = json.loads((tmp_path / "one" / "coordinate_run.json").read_text())["run_id"]

    second = _integrate(coordinate_db, gadm_gpkg, tmp_path / "two", extra=["--replace"])
    assert second.exit_code == 0, second.output
    rebuilt = json.loads((tmp_path / "two" / "coordinate_run.json").read_text())["run_id"]

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        total = connection.execute("SELECT count(*) FROM geo.image_meta_coordinates").fetchone()[0]
        current = connection.execute(
            "SELECT DISTINCT run_id FROM geo.image_meta_coordinates"
        ).fetchone()[0]
    finally:
        connection.close()
    assert total == 13
    assert current == rebuilt != original


def test_integrate_requires_a_source_id_column(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    """A table keyed on nothing is useless, so the run refuses before doing work."""
    setup = duckdb.connect(str(coordinate_db))
    try:
        setup.execute("CREATE TABLE anonymous(decimalLatitude VARCHAR, decimalLongitude VARCHAR)")
        setup.execute("INSERT INTO anonymous VALUES ('5', '5')")
    finally:
        setup.close()

    result = _integrate(
        coordinate_db, gadm_gpkg, tmp_path / "out", table="main.anonymous", into="main.nope"
    )
    assert result.exit_code == 2
    assert "source_id" in result.output

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        existing = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'nope'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert existing == 0


def test_integrate_refuses_to_overwrite_its_own_source(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    """--replace must not be able to destroy the table being read."""
    result = _integrate(
        coordinate_db,
        gadm_gpkg,
        tmp_path / "out",
        into="main.occurrence",
        extra=["--replace"],
    )
    assert result.exit_code == 2

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM main.occurrence").fetchone()[0] == 13
    finally:
        connection.close()


def test_integrate_skips_rows_without_a_source_id(
    coordinate_db: Path, gadm_gpkg: Path, tmp_path: Path
) -> None:
    setup = duckdb.connect(str(coordinate_db))
    try:
        setup.execute(
            """
            CREATE TABLE partial(
                occurrenceID VARCHAR, decimalLatitude VARCHAR, decimalLongitude VARCHAR
            )
            """
        )
        setup.executemany(
            "INSERT INTO partial VALUES (?, ?, ?)",
            [("kept", "5", "5"), (None, "5", "5")],
        )
    finally:
        setup.close()

    result = _integrate(
        coordinate_db, gadm_gpkg, tmp_path / "out", table="main.partial", into="main.partial_geo"
    )
    assert result.exit_code == 0, result.output
    assert "1 rows had no source id" in result.output

    connection = duckdb.connect(str(coordinate_db), read_only=True)
    try:
        rows = connection.execute("SELECT source_id FROM main.partial_geo").fetchall()
    finally:
        connection.close()
    assert rows == [("kept",)]
