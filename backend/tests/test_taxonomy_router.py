"""Tests for the taxonomy code-description endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import taxonomy
from app.services.col_match_codes import (
    MATCH_METHOD_DESCRIPTIONS,
    UPDATE_STATUS_DESCRIPTIONS,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(taxonomy.router)
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
