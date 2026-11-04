"""Tests for the taxonomy code-description and release endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import taxonomy
from app.services.col_match_codes import (
    MATCH_METHOD_DESCRIPTIONS,
    UPDATE_STATUS_DESCRIPTIONS,
)


def build_client(duck_db=None) -> TestClient:
    app = FastAPI()
    app.include_router(taxonomy.router)
    app.state.duck_db = duck_db
    return TestClient(app)


class TestTaxonomyCodes:
    def test_returns_every_group(self):
        response = build_client().get("/taxonomy/codes")
        assert response.status_code == 200
        assert set(response.json()) == {"updateStatus", "matchMethod", "reasonCode"}

    def test_statuses_are_complete(self):
        payload = build_client().get("/taxonomy/codes").json()
        assert payload["updateStatus"] == UPDATE_STATUS_DESCRIPTIONS

    def test_methods_include_prefixed_forms(self):
        methods = build_client().get("/taxonomy/codes").json()["matchMethod"]
        for code in MATCH_METHOD_DESCRIPTIONS:
            assert code in methods
            assert f"GENUS_{code}" in methods
            assert f"SUBSPECIES_{code}" in methods

    def test_descriptions_are_non_empty_strings(self):
        payload = build_client().get("/taxonomy/codes").json()
        for group in payload.values():
            for description in group.values():
                assert isinstance(description, str) and description.strip()


class TestTaxonomyRelease:
    def test_returns_the_recorded_release(self, memory_duckdb):
        memory_duckdb.execute(
            "CREATE TABLE col_release (version VARCHAR, issued VARCHAR, "
            "alias VARCHAR, doi VARCHAR, key VARCHAR, url VARCHAR)"
        )
        memory_duckdb.execute(
            "INSERT INTO col_release VALUES "
            "('2026-10-16 XR', '2026-10-16', 'COL26.10 XR', NULL, '316691', NULL)"
        )
        response = build_client(memory_duckdb).get("/taxonomy/release")

        assert response.status_code == 200
        assert response.json() == {
            "version": "2026-10-16 XR",
            "issued": "2026-10-16",
            "alias": "COL26.10 XR",
            "doi": None,
            "key": "316691",
            "url": None,
        }

    def test_no_release_is_not_found(self, memory_duckdb):
        response = build_client(memory_duckdb).get("/taxonomy/release")

        assert response.status_code == 404
