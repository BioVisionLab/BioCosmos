from pathlib import Path

import duckdb
import numpy as np
import pytest
from conftest import build_collection
from harmonize_core.errors import OutputError
from typer.testing import CliRunner

from morphospace.cli import app
from morphospace.models import MorphospaceParameters
from morphospace.outputs import MorphospaceOutputRepository
from morphospace.pipeline import execute_run

PARAMETERS = MorphospaceParameters(
    min_images=2, bootstrap=20, permutations=19, rarefy_k=3, batch_size=17
)


def _run(collection, output: Path, parameters=PARAMETERS):
    return execute_run(
        database=collection.database,
        lance_dir=collection.lance_dir,
        lance_table=collection.table,
        parameters=parameters,
        reports_dir=None,
        output=output,
    )


def _rows(database: Path, query: str) -> list[tuple]:
    connection = duckdb.connect(str(database), read_only=True)
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def test_scopes_exclude_small_genera_and_unresolved_images(collection, tmp_path):
    result = _run(collection, tmp_path / "run")
    scopes = _rows(result.database_path, "SELECT scope_rank, scope_key FROM scope ORDER BY 1, 2")
    assert scopes == [("all", "all"), ("family", "testidae"), ("genus", "alpha"), ("genus", "beta")]
    species = _rows(result.database_path, "SELECT accepted_species FROM species")
    assert len(species) == 10  # 6 + 3 + 1; the genus-only record is not a species
    assert result.counts["labelled_images"] == 10 * 2 * 4


def test_both_sides_share_one_space(collection, tmp_path):
    result = _run(collection, tmp_path / "run")
    points = _rows(
        result.database_path,
        "SELECT side, count(*) FROM points WHERE scope_key = 'alpha' GROUP BY 1 ORDER BY 1",
    )
    assert points == [("dorsal", 6), ("ventral", 6)]
    basis = _rows(result.database_path, "SELECT basis FROM scope WHERE scope_key = 'alpha'")
    assert basis == [("both_sides",)]


def test_rerun_is_deterministic(collection, tmp_path):
    query = "SELECT pc1, pc2, ell_sx FROM points ORDER BY scope_key, accepted_species, side"
    first = _rows(_run(collection, tmp_path / "a").database_path, query)
    second = _rows(_run(collection, tmp_path / "b").database_path, query)
    assert np.allclose(np.array(first), np.array(second))


def test_medoid_and_dispersion_are_recorded(collection, tmp_path):
    result = _run(collection, tmp_path / "run")
    row = _rows(
        result.database_path,
        "SELECT dorsal_n, dorsal_dispersion, dorsal_img_id, dv_divergence, page_key "
        "FROM species WHERE accepted_species = 'Alpha one'",
    )[0]
    assert row[0] == 4
    assert 0 < row[1] < 0.1
    assert row[2].startswith("alpha_one_dorsal_")
    assert row[3] > 0
    assert row[4] == "alpha_one"


def test_identical_sides_are_fully_integrated(tmp_path):
    collection = build_collection(tmp_path, identical_sides=True)
    result = _run(collection, tmp_path / "run")
    r, divergence = _rows(
        result.database_path,
        "SELECT dv_mantel_r, (SELECT max(dv_divergence) FROM species) "
        "FROM scope WHERE scope_key = 'alpha'",
    )[0]
    assert r > 0.95  # image noise keeps the centroids from being exactly equal
    assert divergence < 0.05


def test_integrate_refuses_to_overwrite_without_replace(collection, tmp_path):
    result = _run(collection, tmp_path / "run")
    backend = tmp_path / "backend.duckdb"
    repository = MorphospaceOutputRepository(result.output_dir)
    report = repository.write_back(backend)
    assert report.tables["main.morphospace_scope"] == 4
    with pytest.raises(OutputError):
        repository.write_back(backend)
    repository.write_back(backend, replace=True)


def test_cli_run_and_integrate(collection, tmp_path):
    runner = CliRunner()
    reports = tmp_path / "reports"
    reports.mkdir()
    common = ["--db", str(collection.database)]
    ran = runner.invoke(
        app,
        [
            "run",
            *common,
            "--lance-dir",
            str(collection.lance_dir),
            "--lance-table",
            "images",
            "--reports-dir",
            str(reports),
            "--min-images",
            "2",
            "--permutations",
            "9",
        ],
    )
    assert ran.exit_code == 0, ran.output
    backend = tmp_path / "backend.duckdb"
    integrated = runner.invoke(
        app, ["integrate", "--db", str(backend), "--reports-dir", str(reports)]
    )
    assert integrated.exit_code == 0, integrated.output
    assert "main.morphospace_points" in integrated.output
    inspected = runner.invoke(app, ["inspect", *common, "--min-images", "2"])
    assert "seen from both sides: 10" in inspected.output


def test_labels_leave_out_excluded_families(collection):
    from morphospace.sources import load_labels

    connection = duckdb.connect(str(collection.database))
    try:
        connection.execute(
            "INSERT INTO image_meta VALUES ('moth_d', 'castnia_x', 'dorsal'), "
            "('moth_v', 'castnia_x', 'ventral')"
        )
        connection.execute(
            "INSERT INTO image_meta_taxonomy VALUES "
            "('moth_d', 'MATCHED', 'Castnia x', 'Castnia x', 'Castniidae'), "
            "('moth_v', 'MATCHED', 'Castnia x', 'Castnia x', ' castniidae ')"
        )
    finally:
        connection.close()

    everything = load_labels(collection.database)
    assert {"moth_d", "moth_v"} <= set(everything.img_id)
    filtered = load_labels(
        collection.database, exclude_families=MorphospaceParameters().exclude_families
    )
    assert not {"moth_d", "moth_v"} & set(filtered.img_id)
    assert len(filtered) == len(everything) - 2
