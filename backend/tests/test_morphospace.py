"""The morphospace endpoints, over tables shaped like `morphospace integrate` writes."""

import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.query.morphospace import MorphospaceQuery
from app.routers.morphospace import router

RUN = "run-1"

DDL = [
    """CREATE TABLE morphospace_scope (
        scope_rank VARCHAR, scope_key VARCHAR, scope_name VARCHAR, parent_family VARCHAR,
        n_species BIGINT, n_species_both BIGINT, basis VARCHAR,
        explained_pc1 DOUBLE, explained_pc2 DOUBLE, explained_pc3 DOUBLE,
        dv_mantel_n BIGINT, dv_mantel_r DOUBLE, dv_mantel_p DOUBLE, run_id VARCHAR)""",
    """CREATE TABLE morphospace_points (
        scope_rank VARCHAR, scope_key VARCHAR, accepted_species VARCHAR, page_key VARCHAR,
        genus_key VARCHAR, family_key VARCHAR, side VARCHAR, n_images BIGINT,
        pc1 DOUBLE, pc2 DOUBLE, pc3 DOUBLE, ell_x DOUBLE, ell_y DOUBLE,
        ell_sx DOUBLE, ell_sy DOUBLE, ell_rho DOUBLE, img_id VARCHAR)""",
    """CREATE TABLE morphospace_species (
        accepted_species VARCHAR, page_key VARCHAR, genus_key VARCHAR, genus_name VARCHAR,
        family_key VARCHAR, family_name VARCHAR,
        dorsal_n BIGINT, dorsal_dispersion DOUBLE, dorsal_img_id VARCHAR,
        ventral_n BIGINT, ventral_dispersion DOUBLE, ventral_img_id VARCHAR,
        dv_divergence DOUBLE)""",
    """CREATE TABLE morphospace_disparity (
        scope_rank VARCHAR, scope_key VARCHAR, side VARCHAR, n_species BIGINT,
        sum_var DOUBLE, rarefied_mean DOUBLE, rarefied_low DOUBLE, rarefied_high DOUBLE,
        rarefy_k BIGINT)""",
    """CREATE TABLE morphospace_extremes (
        scope_rank VARCHAR, scope_key VARCHAR, axis VARCHAR, "end" VARCHAR,
        accepted_species VARCHAR, page_key VARCHAR, side VARCHAR, img_id VARCHAR,
        value DOUBLE)""",
]

SPECIES = [
    # species, genus, dorsal dispersion, ventral dispersion, dv divergence
    ("Danaus plexippus", "danaus", 0.02, 0.03, 0.10),
    ("Danaus gilippus", "danaus", 0.04, None, None),
    ("Danaus chrysippus", "danaus", 0.06, 0.01, 0.30),
    ("Euploea core", "euploea", 0.05, 0.05, 0.20),
]


def _seed(client):
    for statement in DDL:
        client.execute(statement)
    for rank, key, name, parent in (
        ("family", "nymphalidae", "Nymphalidae", None),
        ("genus", "danaus", "Danaus", "Nymphalidae"),
    ):
        client.execute_prepared(
            "INSERT INTO morphospace_scope VALUES (?, ?, ?, ?, 3, 2, 'both_sides', "
            "0.31234567, 0.2, 0.1, 2, 0.5, 0.01, ?)",
            [rank, key, name, parent, RUN],
        )
        for side in ("dorsal", "ventral"):
            client.execute_prepared(
                "INSERT INTO morphospace_disparity VALUES (?, ?, ?, 3, 0.1, 0.1, 0.05, 0.2, 5)",
                [rank, key, side],
            )
        client.execute_prepared(
            "INSERT INTO morphospace_extremes VALUES "
            "(?, ?, 'pc1', 'max', 'Danaus plexippus', 'danaus_plexippus', 'dorsal', 'img-1', 1.5)",
            [rank, key],
        )
    for species, genus, dorsal, ventral, divergence in SPECIES:
        page = species.lower().replace(" ", "_")
        client.execute_prepared(
            "INSERT INTO morphospace_species VALUES "
            "(?, ?, ?, ?, 'nymphalidae', 'Nymphalidae', ?, ?, ?, ?, ?, ?, ?)",
            [
                species,
                page,
                genus,
                genus.title(),
                4,
                dorsal,
                f"{page}-d",
                None if ventral is None else 4,
                ventral,
                None if ventral is None else f"{page}-v",
                divergence,
            ],
        )
        for side in ("dorsal", "ventral"):
            client.execute_prepared(
                "INSERT INTO morphospace_points VALUES "
                "('genus', 'danaus', ?, ?, ?, 'nymphalidae', ?, 4, "
                "0.123456789, -0.5, 0.0, 0.1, -0.4, 0.02, 0.03, 'NaN', ?)",
                [species, page, genus, side, f"{page}-{side[0]}"],
            )
    return client


@pytest.fixture
def api(memory_duckdb):
    app = FastAPI()
    app.include_router(router)
    app.state.duck_db = _seed(memory_duckdb)
    return TestClient(app)


def test_scope_is_columnar_and_rounded(api):
    response = api.get("/morphospace/genus/Danaus")
    assert response.status_code == 200
    assert "max-age=86400" in response.headers["Cache-Control"]
    assert response.headers["ETag"] == f'W/"{RUN}-genus-danaus"'
    body = response.json()
    assert body["scope"]["explained"][0] == 0.3123
    assert body["scope"]["integration"] == {"n": 2, "r": 0.5, "p": 0.01}
    points = body["points"]
    assert len(points["species"]) == len(points["pc1"]) == 8
    assert points["pc1"][0] == 0.1235
    assert points["ellRho"][0] is None  # NaN is not valid JSON
    assert set(body["disparity"]) == {"dorsal", "ventral"}
    assert body["extremes"][0]["pageKey"] == "danaus_plexippus"
    assert body["children"] == []


def test_family_lists_its_genera(api):
    body = api.get("/morphospace/family/nymphalidae").json()
    (genus,) = body["children"]
    assert genus["key"] == "danaus"
    assert genus["disparity"]["ventral"]["rarefiedMean"] == 0.1


def test_species_percentiles_within_genus(api):
    body = api.get("/morphospace/species/danaus_plexippus").json()
    assert body["species"] == "Danaus plexippus"
    assert body["genus"] == {
        "key": "danaus",
        "name": "Danaus",
        "available": True,
        "nSpecies": 3,
    }
    # Lowest dorsal dispersion of three: percentile 0. Ventral ranks only the
    # two Danaus measured from below.
    assert body["sides"]["dorsal"]["percentile"]["genus"] == 0.0
    assert body["sides"]["ventral"]["percentile"]["genus"] == 1.0
    assert math.isclose(body["dvDivergencePercentile"]["family"], 0.0)


def test_species_alone_in_its_genus_has_no_genus_percentile(api):
    body = api.get("/morphospace/species/euploea_core").json()
    assert body["sides"]["dorsal"]["percentile"]["genus"] is None
    assert body["dvDivergencePercentile"]["genus"] is None
    # Its family still has others to rank against.
    assert body["sides"]["dorsal"]["percentile"]["family"] is not None


def test_species_without_a_ventral_side(api):
    body = api.get("/morphospace/species/Danaus gilippus").json()
    assert body["sides"]["ventral"] is None
    assert body["dvDivergence"] is None


@pytest.mark.parametrize(
    "path",
    ["/morphospace/genus/unknown", "/morphospace/species/unknown_species"],
)
def test_unknown_is_not_found_and_not_cached(api, path):
    response = api.get(path)
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


def test_unknown_rank_is_rejected(api):
    assert api.get("/morphospace/order/lepidoptera").status_code == 422


def test_missing_tables_are_not_found(memory_duckdb):
    assert MorphospaceQuery(memory_duckdb).get_scope("family", "nymphalidae") is None
    assert MorphospaceQuery(memory_duckdb).get_species("danaus_plexippus") is None
