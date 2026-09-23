"""Featured species: completeness scoring, the daily sample, and the route."""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.query import featured_species as featured_module
from app.query.featured_species import FeaturedSpecies, seconds_until_rotation
from app.routers.species_data import get_featured_species, router

IMAGE_DDL = """
    CREATE TABLE image_meta (
        img_id VARCHAR, species VARCHAR, class_dv VARCHAR,
        confidence_dv DOUBLE, common_name VARCHAR
    )
"""
TAXONOMY_DDL = """
    CREATE TABLE image_meta_taxonomy (
        img_id VARCHAR, update_status VARCHAR, accepted_species_name VARCHAR,
        accepted_rank VARCHAR, accepted_name VARCHAR, accepted_id VARCHAR,
        accepted_family VARCHAR
    )
"""
OPTIONAL_DDL = [
    "CREATE TABLE image_meta_coordinates (source_id VARCHAR, country_check VARCHAR)",
    "CREATE TABLE image_meta_provenance (img_id VARCHAR, catalog_number VARCHAR)",
    "CREATE TABLE col_vernacular (usage_id VARCHAR, vernacular_name VARCHAR)",
    'CREATE TABLE lep_traits_consensus ("Species" VARCHAR)',
    "CREATE TABLE col_type_material (name_id VARCHAR)",
    "CREATE TABLE species_similarity (species VARCHAR)",
]


def _add_species(
    db,
    slug: str,
    accepted: str,
    accepted_id: str,
    *,
    images: int = 1,
    ventral: bool = False,
    located: bool = False,
    catalogued: bool = False,
    status: str = "MATCHED",
):
    for index in range(images):
        img_id = f"{slug}-{index}"
        side = "ventral" if ventral and index == 0 else "dorsal"
        db.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, ?, ?, NULL)",
            [img_id, slug, side, 0.5 + index / 1000],
        )
        db.execute_prepared(
            "INSERT INTO image_meta_taxonomy VALUES (?, ?, ?, 'species', ?, ?, 'Nymphalidae')",
            [img_id, status, accepted, accepted, accepted_id],
        )
        if located:
            db.execute_prepared(
                "INSERT INTO image_meta_coordinates VALUES (?, 'COUNTRY_MATCH')",
                [img_id],
            )
        if catalogued:
            db.execute_prepared(
                "INSERT INTO image_meta_provenance VALUES (?, 'CAT-1')", [img_id]
            )


@pytest.fixture
def seeded(memory_duckdb):
    db = memory_duckdb
    db.execute(IMAGE_DDL)
    db.execute(TAXONOMY_DDL)
    for ddl in OPTIONAL_DDL:
        db.execute(ddl)
    # Every facet.
    _add_species(
        db,
        "danaus_plexippus",
        "Danaus plexippus",
        "DP",
        images=25,
        ventral=True,
        located=True,
        catalogued=True,
    )
    db.execute("INSERT INTO col_vernacular VALUES ('DP', 'Monarch')")
    db.execute("INSERT INTO lep_traits_consensus VALUES ('Danaus plexippus')")
    db.execute("INSERT INTO col_type_material VALUES ('DP')")
    db.execute("INSERT INTO species_similarity VALUES ('danaus_plexippus')")
    # Two facets: distribution and specimens.
    _add_species(
        db,
        "vanessa_cardui",
        "Vanessa cardui",
        "VC",
        images=3,
        located=True,
        catalogued=True,
    )
    # One facet: traits, matched case-insensitively on the accepted name.
    _add_species(db, "papilio_machaon", "Papilio machaon", "PM", images=2)
    db.execute("INSERT INTO lep_traits_consensus VALUES ('PAPILIO MACHAON')")
    # Nothing, and an unresolved record that must not be scored at all.
    _add_species(db, "pieris_rapae", "Pieris rapae", "PR")
    _add_species(db, "unknown_sp", "Unknown sp", "UN", status="AMBIGUOUS")
    return db


def _scores(db):
    return {row["species"]: row for row in FeaturedSpecies(db)._load().to_dicts()}


def test_scores_one_point_per_facet(seeded):
    scores = _scores(seeded)
    assert "Unknown sp" not in scores
    assert scores["Danaus plexippus"]["score"] == 8
    assert scores["Vanessa cardui"]["score"] == 2
    assert scores["Papilio machaon"]["score"] == 1
    assert scores["Pieris rapae"]["score"] == 0


def test_leads_with_the_most_confident_dorsal_image(seeded):
    # Index 0 is the ventral image; the last dorsal one is the most confident.
    assert _scores(seeded)["Danaus plexippus"]["img_id"] == "danaus_plexippus-24"


def test_missing_optional_tables_score_zero(memory_duckdb):
    memory_duckdb.execute(IMAGE_DDL)
    memory_duckdb.execute(TAXONOMY_DDL)
    _add_species(memory_duckdb, "danaus_plexippus", "Danaus plexippus", "DP", images=25)
    row = _scores(memory_duckdb)["Danaus plexippus"]
    assert row["score"] == 1
    assert row["images"] is True


def test_missing_required_tables_degrade_to_none(memory_duckdb):
    assert FeaturedSpecies(memory_duckdb).sample() is None


def test_pool_takes_whole_tiers_until_the_minimum(seeded, monkeypatch):
    service = FeaturedSpecies(seeded)
    monkeypatch.setattr(featured_module, "MIN_POOL", 1)
    assert set(service._pool()["species"]) == {"Danaus plexippus"}
    monkeypatch.setattr(featured_module, "MIN_POOL", 2)
    assert set(service._pool()["species"]) == {"Danaus plexippus", "Vanessa cardui"}
    monkeypatch.setattr(featured_module, "MIN_POOL", 100)
    assert service._pool().height == 4


def test_sample_is_stable_for_a_day_and_extends_with_limit(seeded, monkeypatch):
    monkeypatch.setattr(featured_module, "MIN_POOL", 100)
    service = FeaturedSpecies(seeded)
    day = date(2026, 9, 23)
    two = service.sample(2, day)
    assert two == service.sample(2, day)
    four = service.sample(4, day)
    assert [s["slug"] for s in four["species"][:2]] == [
        s["slug"] for s in two["species"]
    ]
    assert four["poolSize"] == 4
    assert four["date"] == "2026-09-23"
    # The limit is capped by the pool rather than failing.
    assert len(service.sample(24, day)["species"]) == 4


def test_sample_payload_names_the_facets(seeded, monkeypatch):
    monkeypatch.setattr(featured_module, "MIN_POOL", 1)
    species = FeaturedSpecies(seeded).sample(6, date(2026, 1, 1))["species"]
    assert species == [
        {
            "species": "Danaus plexippus",
            "slug": "danaus_plexippus",
            "family": "Nymphalidae",
            "imgId": "danaus_plexippus-24",
            "imageCount": 25,
            "score": 8,
            "facets": list(featured_module.FACETS),
        }
    ]


def test_rotation_is_at_utc_midnight():
    assert seconds_until_rotation(datetime(2026, 9, 23, 23, 59, 0, tzinfo=UTC)) == 60
    assert seconds_until_rotation(datetime(2026, 9, 23, 0, 0, 0, tzinfo=UTC)) == 86400


def _client(service) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_featured_species] = lambda: service
    return TestClient(app)


def test_route_is_cached_until_rotation(seeded):
    response = _client(FeaturedSpecies(seeded)).get("/species/featured?limit=2")
    assert response.status_code == 200
    cache_control = response.headers["cache-control"]
    max_age = int(cache_control.split("max-age=")[1].split(",")[0])
    assert 0 < max_age <= 86400
    assert len(response.json()["species"]) >= 1


@pytest.mark.parametrize("limit", [0, 25])
def test_route_rejects_out_of_range_limits(seeded, limit):
    response = _client(FeaturedSpecies(seeded)).get(f"/species/featured?limit={limit}")
    assert response.status_code == 422


def test_route_404s_without_records(memory_duckdb):
    response = _client(FeaturedSpecies(memory_duckdb)).get("/species/featured")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_dependency_reuses_one_instance(memory_duckdb):
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(duck_db=memory_duckdb))
    )
    assert get_featured_species(request) is get_featured_species(request)
