from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import geography


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(geography.router)
    return TestClient(app)


def test_codes_endpoint_serves_every_group():
    response = build_client().get("/geography/codes")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "validationStatus",
        "coordinateCheck",
        "countryCheck",
        "adm1Check",
    }
    assert payload["validationStatus"]["COUNTRY_MISMATCH"]
    assert len(payload["validationStatus"]) == 8


def test_every_description_is_prose():
    payload = build_client().get("/geography/codes").json()
    for group, codes in payload.items():
        for code, description in codes.items():
            assert isinstance(description, str) and description.strip(), (group, code)
