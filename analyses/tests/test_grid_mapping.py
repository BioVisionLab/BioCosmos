"""Check validated-image eligibility and species deduplication on the area grid."""

import duckdb
import matplotlib.pyplot as plt
import pytest
from analyses.helpers.grid_mapping import CELL_SIZE_M, ZERO_COLOR, grid_map, validated_grid
from analyses.helpers.publication import AnalysisError, project_root
from matplotlib.colors import to_rgba
from pyproj import Transformer


def test_grid_counts_validated_images_and_unique_species(settings):
    grid = validated_grid(settings)
    assert grid.image_count.tolist() == [2]
    assert grid.species_count.tolist() == [1]
    assert grid.identified_image_count.tolist() == [2]
    assert grid.cell_area_km2.tolist() == [10_000]
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute(
            "INSERT INTO image_meta_coordinates "
            "VALUES ('i8', 'VALID', 'COUNTRY_MATCH', 40, -100, 'USA', 'United States')"
        )
    grid = validated_grid(settings)
    assert grid.image_count.sum() == 3
    assert grid.species_count.sum() == 1
    assert grid.identified_image_count.sum() == 2


def test_grid_uses_validated_coordinates_not_raw_image_fields(settings):
    # Raw image fields say (10, 20); the validation table places i1/i2 at (40, -100).
    grid = validated_grid(settings)
    projection = Transformer.from_crs("EPSG:4326", "EPSG:8857", always_xy=True)
    x, y = projection.transform(-100, 40)
    assert grid.x_min_m.item() <= x < grid.x_min_m.item() + CELL_SIZE_M
    assert grid.y_min_m.item() <= y < grid.y_min_m.item() + CELL_SIZE_M


def test_zero_richness_cells_are_drawn_apart_from_the_log_scale(settings):
    with duckdb.connect(str(settings.database)) as connection:
        # i4 is AMBIGUOUS: an occupied cell with no accepted species.
        connection.execute(
            "UPDATE image_meta_coordinates SET validation_status = 'VALID', "
            "latitude = -30, longitude = 140 WHERE source_id = 'i4'"
        )
    grid = validated_grid(settings)
    assert sorted(grid.species_count) == [0, 1]
    fig, ax = plt.subplots()
    collection = grid_map(ax, grid, project_root(), "species_count")
    colors = collection.to_rgba(collection.get_array())
    zero = grid.species_count.to_numpy() == 0
    assert tuple(colors[zero][0]) == to_rgba(ZERO_COLOR)
    assert tuple(colors[~zero][0]) != to_rgba(ZERO_COLOR)
    plt.close(fig)


def test_invalid_coordinate_marked_valid_raises(settings):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute("UPDATE image_meta_coordinates SET validation_status = 'VALID'")
    with pytest.raises(AnalysisError, match="unusable coordinates"):
        validated_grid(settings)


def test_empty_validated_population_raises(settings):
    with duckdb.connect(str(settings.database)) as connection:
        connection.execute("DELETE FROM image_meta_coordinates")
    with pytest.raises(AnalysisError, match="No images"):
        validated_grid(settings)
