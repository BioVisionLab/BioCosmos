"""Memory caps on DuckDB, LanceDB, and uploaded query images."""

import io
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.configs.config import get_duck_db_settings, get_lance_cache_sizes
from app.database.duckdb import DuckDBClient
from app.database.lance import LanceDB
from app.main import app
from app.query import image_search
from app.query.image_search import MAX_UPLOAD_PIXELS, image_too_large

client = TestClient(app)


def _config(duck: dict, lance: dict) -> dict:
    return {
        "db": {
            "duck": {"file": "test.duckdb", **duck},
            "lance": {"file": "test.lance", **lance},
        }
    }


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="PNG")

    return buffer.getvalue()


def test_duck_settings_read_from_config():
    config = _config({"memory_limit": "2GB", "threads": 4}, {})

    with patch("app.configs.config.load_config", return_value=config):
        assert get_duck_db_settings() == {"memory_limit": "2GB", "threads": 4}


def test_duck_settings_leave_out_null_values():
    config = _config({"memory_limit": None, "threads": None}, {})

    with patch("app.configs.config.load_config", return_value=config):
        assert get_duck_db_settings() == {}


def test_lance_cache_sizes_in_bytes():
    config = _config({}, {"index_cache_mb": 2, "metadata_cache_mb": None})

    with patch("app.configs.config.load_config", return_value=config):
        assert get_lance_cache_sizes() == (2 * 1024 * 1024, None)


def test_duckdb_client_applies_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCK_DIR", str(tmp_path))
    config = _config({"memory_limit": "1GB", "threads": 2}, {})

    with patch("app.configs.config.load_config", return_value=config):
        duck_db = DuckDBClient()

    try:
        threads = duck_db.execute("SELECT current_setting('threads')").fetchone()
        limit = duck_db.execute("SELECT current_setting('memory_limit')").fetchone()
    finally:
        duck_db.close()

    assert threads == (2,)
    # DuckDB reports the limit in its own units (1GB is 953.6 MiB).
    assert limit is not None and limit[0].endswith("MiB")


def test_lance_client_connects_with_cache_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("LANCE_DIR", str(tmp_path))
    config = _config({}, {"index_cache_mb": 64, "metadata_cache_mb": 16})

    with patch("app.configs.config.load_config", return_value=config):
        lance_db = LanceDB()

    assert lance_db.create_or_get_collection("images").count_rows() == 0


def test_small_image_is_not_too_large():
    assert not image_too_large(_png(64, 64))


def test_image_over_pixel_limit_is_too_large(monkeypatch):
    monkeypatch.setattr(image_search, "MAX_UPLOAD_PIXELS", 100)

    assert image_too_large(_png(20, 20))


def test_unreadable_bytes_are_left_to_verification():
    assert not image_too_large(b"not an image")


def test_pixel_limit_allows_common_photos():
    assert 6000 * 4000 <= MAX_UPLOAD_PIXELS


def test_image_search_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr("app.routers.ml_search.MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/search/image",
        files={"file": ("big.png", _png(64, 64), "image/png")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["error"]


def test_image_search_rejects_too_many_pixels(monkeypatch):
    monkeypatch.setattr(image_search, "MAX_UPLOAD_PIXELS", 100)
    response = client.post(
        "/search/image",
        files={"file": ("wide.png", _png(20, 20), "image/png")},
    )

    assert response.status_code == 413
