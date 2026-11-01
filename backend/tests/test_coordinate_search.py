"""Tests for the coordinate search radius.

A coordinate search matches images within a great-circle distance of the
point, not a latitude/longitude box, so the cases sit just either side of the
50 km radius: on the equator, across the antimeridian, near a pole, and in the
corner of the box the search used to draw.
"""

import math

import pytest

from app.services.metadata import (
    EARTH_RADIUS_KM,
    ImageMetaService,
    coordinate_prefilter,
)
from tests.test_specimen_taxonomy import OCCURRENCE_DDL, build_service

RADIUS_KM = 50.0

# Degrees of arc along a great circle per kilometer.
DEGREES_PER_KM = 180.0 / (math.pi * EARTH_RADIUS_KM)

INSIDE_DEG = 49.9 * DEGREES_PER_KM
OUTSIDE_DEG = 50.1 * DEGREES_PER_KM

# (img_id, lat, lon). Each group is far enough from the others that no search
# below reaches into another group.
POINTS = [
    # Equator, along the meridian and the parallel.
    ("eq_north_in", INSIDE_DEG, 0.0),
    ("eq_north_out", OUTSIDE_DEG, 0.0),
    ("eq_east_in", 0.0, INSIDE_DEG),
    ("eq_east_out", 0.0, OUTSIDE_DEG),
    # 45 km north and 45 km east: inside the old box, about 64 km away.
    ("eq_corner", 45 * DEGREES_PER_KM, 45 * DEGREES_PER_KM),
    # Across the antimeridian from a search at (10, 179.9).
    ("am_west_in", 10.0, -180.0 + (INSIDE_DEG / math.cos(math.radians(10.0)) - 0.1)),
    ("am_west_out", 10.0, -180.0 + (OUTSIDE_DEG / math.cos(math.radians(10.0)) - 0.1)),
    # Over the North Pole from a search at (89.8, 0).
    ("pole_far_side_in", 89.8, 180.0),
    ("pole_far_side_out", 90.0 - (OUTSIDE_DEG - 0.2), 180.0),
]


def seed_points(client) -> None:
    client.execute(OCCURRENCE_DDL)

    for img_id, lat, lon in POINTS:
        client.execute_prepared(
            "INSERT INTO image_meta VALUES (?, 'danaus_plexippus', 'nymphalidae',"
            " NULL, NULL, NULL, 'dorsal', ?, ?, 'gbif', 'Animalia', 'Arthropoda',"
            " 'Insecta', 'Lepidoptera')",
            [img_id, lat, lon],
        )


@pytest.fixture
def service(memory_duckdb) -> ImageMetaService:
    seed_points(memory_duckdb)

    return build_service(memory_duckdb)


def found(service: ImageMetaService, lat: float, lon: float) -> set[str]:
    _, specimens, total = service.search_by_coordinate(lat, lon, RADIUS_KM, 50, 0)
    assert total == len(specimens)

    return set(specimens["img_id"].to_list())


def test_points_on_the_equator(service):
    assert found(service, 0.0, 0.0) == {"eq_north_in", "eq_east_in"}


def test_box_corner_is_out_of_reach(service):
    assert "eq_corner" not in found(service, 0.0, 0.0)


def test_points_across_the_antimeridian(service):
    assert found(service, 10.0, 179.9) == {"am_west_in"}


def test_points_over_the_pole(service):
    assert found(service, 89.8, 0.0) == {"pole_far_side_in"}


def test_specimens_come_nearest_first(service):
    _, specimens, _ = service.search_by_coordinate(OUTSIDE_DEG, 0.0, RADIUS_KM, 50, 0)
    assert specimens["img_id"].to_list()[:2] == ["eq_north_out", "eq_north_in"]


def test_species_list_follows_the_radius(service):
    results, _, _ = service.search_by_coordinate(0.0, 90.0, RADIUS_KM, 50, 0)
    assert results.is_empty()


class TestCoordinatePrefilter:
    """The coarse box must hold the whole circle, wherever it falls."""

    def test_away_from_the_edges_is_one_range(self):
        lat_min, lat_max, lon_ranges = coordinate_prefilter(0.0, 0.0, RADIUS_KM)
        assert lat_min == pytest.approx(-RADIUS_KM * DEGREES_PER_KM)
        assert lat_max == pytest.approx(RADIUS_KM * DEGREES_PER_KM)
        assert len(lon_ranges) == 1
        lon_min, lon_max = lon_ranges[0]
        assert lon_max == pytest.approx(RADIUS_KM * DEGREES_PER_KM)
        assert lon_min == pytest.approx(-lon_max)

    def test_widens_with_latitude(self):
        _, _, [(_, equator)] = coordinate_prefilter(0.0, 0.0, RADIUS_KM)
        _, _, [(_, sixty)] = coordinate_prefilter(60.0, 0.0, RADIUS_KM)
        assert sixty == pytest.approx(2 * equator, rel=1e-3)

    @pytest.mark.parametrize("lon", [179.9, -179.9])
    def test_splits_at_the_antimeridian(self, lon):
        _, _, lon_ranges = coordinate_prefilter(0.0, lon, RADIUS_KM)
        assert len(lon_ranges) == 2
        assert (180.0 in lon_ranges[0]) or (180.0 in lon_ranges[1])
        assert (-180.0 in lon_ranges[0]) or (-180.0 in lon_ranges[1])

        for lon_min, lon_max in lon_ranges:
            assert -180.0 <= lon_min <= lon_max <= 180.0

    @pytest.mark.parametrize("lat", [90.0, 89.8, -89.8, -90.0])
    def test_spans_every_longitude_at_a_pole(self, lat):
        lat_min, lat_max, lon_ranges = coordinate_prefilter(lat, 0.0, RADIUS_KM)
        assert lon_ranges == [(-180.0, 180.0)]
        assert -90.0 <= lat_min <= lat_max <= 90.0
