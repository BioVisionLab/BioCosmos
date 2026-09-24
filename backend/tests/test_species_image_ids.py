"""Tests for the species image-ID page ImageMetaService serves the gallery.

Run against a real in-memory DuckDB: the ordering lives in the SQL.
"""

import pytest

from app.services.metadata import ImageMetaService


@pytest.fixture
def service(memory_duckdb):
    memory_duckdb.execute(
        "CREATE TABLE image_meta (img_id VARCHAR, species VARCHAR, class_dv VARCHAR)"
    )
    for row in [
        ("a_1", "danaus_plexippus", "ventral"),
        ("a_2", "danaus_plexippus", "Dorsal"),
        ("b_1", "danaus_plexippus", "ventral"),
        ("b_2", "danaus_plexippus", "dorsal"),
        ("c_1", "danaus_plexippus", None),
        ("c_2", "danaus_plexippus", "dorsal"),
        ("z_1", "colias_eurytheme", "dorsal"),
    ]:
        memory_duckdb.execute_prepared(
            "INSERT INTO image_meta VALUES (?, ?, ?)", list(row)
        )
    meta = ImageMetaService.__new__(ImageMetaService)
    meta.table = "image_meta"
    meta.db_client = memory_duckdb
    return meta


def test_default_order_is_by_image_id(service):
    ids = service.get_image_ids_by_species("danaus_plexippus", limit=10)
    assert ids == ["a_1", "a_2", "b_1", "b_2", "c_1", "c_2"]


def test_view_order_puts_dorsal_before_ventral(service):
    ids = service.get_image_ids_by_species(
        "danaus_plexippus", limit=10, view_order=True
    )
    assert ids == ["a_2", "b_2", "c_2", "a_1", "b_1", "c_1"]


def test_view_order_only_reorders_within_the_page(service):
    # The page is still cut by image ID, so it holds the same images as the
    # unsorted page rather than the first four dorsal images overall.
    ids = service.get_image_ids_by_species(
        "danaus_plexippus", limit=4, offset=0, view_order=True
    )
    assert ids == ["a_2", "b_2", "a_1", "b_1"]
