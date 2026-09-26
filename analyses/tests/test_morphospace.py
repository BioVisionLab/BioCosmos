"""The morphospace figure reads integrated tables and draws every panel."""

from dataclasses import replace

import duckdb
import matplotlib.pyplot as plt
import nbformat
import numpy as np
import pytest
from analyses.helpers.morphospace import (
    disparity_panel,
    integration_panel,
    morphospace_panel,
    morphospace_summaries,
    variation_panel,
)
from analyses.helpers.publication import AnalysisError, load_settings, project_root
from nbclient import NotebookClient

GENERA = {"alpha": "Aidae", "beta": "Aidae", "gamma": "Bidae", "delta": "Bidae"}
SPECIES_PER_GENUS = 6


def _seed(database):
    rng = np.random.default_rng(0)
    scope, points, species, disparity = [], [], [], []

    def scope_row(rank, key, name, parent, n, r, p):
        scope.append((rank, key, name, parent, n, n, "both_sides", 0.3, 0.2, 0.1, n, r, p, "run"))
        for side in ("dorsal", "ventral"):
            mean = float(rng.uniform(0.02, 0.1))
            disparity.append((rank, key, side, n, mean, mean, mean - 0.01, mean + 0.01, 5))

    for genus, family in GENERA.items():
        scope_row("genus", genus, genus.title(), family, SPECIES_PER_GENUS, 0.6, 0.01)
        for number in range(SPECIES_PER_GENUS):
            name = f"{genus.title()} s{number}"
            species.append(
                (
                    name,
                    f"{genus}_s{number}",
                    genus,
                    genus.title(),
                    family.lower(),
                    family,
                    4,
                    float(rng.uniform(0.01, 0.05)),
                    "d",
                    4,
                    float(rng.uniform(0.01, 0.05)),
                    "v",
                    float(rng.uniform(0.0, 0.2)),
                )
            )
            for side in ("dorsal", "ventral"):
                x, y = rng.normal(size=2)
                points.append(
                    (
                        "all",
                        "all",
                        name,
                        f"{genus}_s{number}",
                        genus,
                        family.lower(),
                        side,
                        4,
                        x,
                        y,
                        0.0,
                        x,
                        y,
                        0.1,
                        0.1,
                        0.0,
                        "img",
                    )
                )
    scope_row("all", "all", "All species", None, len(species), 0.7, None)

    with duckdb.connect(str(database)) as connection:
        connection.execute("""
            CREATE TABLE morphospace_scope (
                scope_rank VARCHAR, scope_key VARCHAR, scope_name VARCHAR,
                parent_family VARCHAR, n_species BIGINT, n_species_both BIGINT,
                basis VARCHAR, explained_pc1 DOUBLE, explained_pc2 DOUBLE,
                explained_pc3 DOUBLE, dv_mantel_n BIGINT, dv_mantel_r DOUBLE,
                dv_mantel_p DOUBLE, run_id VARCHAR);
            CREATE TABLE morphospace_points (
                scope_rank VARCHAR, scope_key VARCHAR, accepted_species VARCHAR,
                page_key VARCHAR, genus_key VARCHAR, family_key VARCHAR, side VARCHAR,
                n_images BIGINT, pc1 DOUBLE, pc2 DOUBLE, pc3 DOUBLE, ell_x DOUBLE,
                ell_y DOUBLE, ell_sx DOUBLE, ell_sy DOUBLE, ell_rho DOUBLE, img_id VARCHAR);
            CREATE TABLE morphospace_species (
                accepted_species VARCHAR, page_key VARCHAR, genus_key VARCHAR,
                genus_name VARCHAR, family_key VARCHAR, family_name VARCHAR,
                dorsal_n BIGINT, dorsal_dispersion DOUBLE, dorsal_img_id VARCHAR,
                ventral_n BIGINT, ventral_dispersion DOUBLE, ventral_img_id VARCHAR,
                dv_divergence DOUBLE);
            CREATE TABLE morphospace_disparity (
                scope_rank VARCHAR, scope_key VARCHAR, side VARCHAR, n_species BIGINT,
                sum_var DOUBLE, rarefied_mean DOUBLE, rarefied_low DOUBLE,
                rarefied_high DOUBLE, rarefy_k BIGINT);
            CREATE TABLE morphospace_extremes (
                scope_rank VARCHAR, scope_key VARCHAR, axis VARCHAR, "end" VARCHAR,
                accepted_species VARCHAR, page_key VARCHAR, side VARCHAR, img_id VARCHAR,
                value DOUBLE);
        """)
        connection.executemany(
            f"INSERT INTO morphospace_scope VALUES ({', '.join('?' * 14)})", scope
        )
        connection.executemany(
            f"INSERT INTO morphospace_points VALUES ({', '.join('?' * 17)})", points
        )
        connection.executemany(
            f"INSERT INTO morphospace_species VALUES ({', '.join('?' * 13)})", species
        )
        connection.executemany(
            f"INSERT INTO morphospace_disparity VALUES ({', '.join('?' * 9)})", disparity
        )


@pytest.fixture
def morpho_settings(tmp_path):
    database = tmp_path / "biocosmos.duckdb"
    _seed(database)
    return replace(load_settings(), database=database, output=tmp_path / "figures")


def test_summaries_have_one_row_per_panel_unit(morpho_settings):
    summaries = morphospace_summaries(morpho_settings)
    total = len(GENERA) * SPECIES_PER_GENUS
    assert summaries["scope"].iloc[0]["n_species"] == total
    assert len(summaries["points"]) == total * 2
    assert set(summaries["disparity"]["genus"]) == set(GENERA)
    assert {"dorsal_mean", "ventral_low", "ventral_high"} <= set(summaries["disparity"])
    assert len(summaries["integration"]) == len(GENERA)
    assert len(summaries["species"]) == total


def test_every_panel_draws(morpho_settings):
    summaries = morphospace_summaries(morpho_settings)
    fig, axes = plt.subplots(2, 2)
    colors = morphospace_panel(axes[0, 0], summaries["points"], summaries["scope"].iloc[0])
    assert set(colors) == {"aidae", "bidae"}  # coloured by family in the "all" scope
    assert colors["aidae"] == ("#1b9e77", "o")  # the site's first Dark2 slot and shape
    disparity_panel(axes[0, 1], summaries["disparity"])
    integration_panel(axes[1, 0], summaries["integration"], 0.7)
    variation_panel(axes[1, 1], summaries["species"])
    plt.close(fig)


def test_unknown_scope_is_an_error(morpho_settings):
    with pytest.raises(AnalysisError, match="No morphospace"):
        morphospace_summaries(morpho_settings, scope_rank="family", scope_key="nope")


def test_missing_tables_point_at_integrate(settings):
    with pytest.raises(AnalysisError, match="morphospace integrate"):
        morphospace_summaries(settings)


def test_notebook_executes_with_fixture_data(morpho_settings, monkeypatch):
    root = project_root()
    output = root / "analyses/results/fixture-validation"
    output.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DUCK_DIR", str(morpho_settings.database.parent))
    monkeypatch.setenv("BIOCOSMOS_ANALYSES_OUTPUT", str(output))
    monkeypatch.setenv("MPLBACKEND", "Agg")
    notebook_path = root / "analyses/notebooks/morphospace.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    nbformat.validate(notebook)
    before = notebook_path.read_bytes()
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(root / "analyses/notebooks")}},
    ).execute()
    assert notebook_path.read_bytes() == before
    for suffix in ("pdf", "png", "svg"):
        assert (output / f"morphospace.{suffix}").is_file()
    assert (output / "morphospace_disparity.csv").is_file()
