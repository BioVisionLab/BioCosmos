"""Equal-area image abundance and accepted-species richness maps."""

import json

import numpy as np
from matplotlib import colormaps
from matplotlib.collections import PatchCollection
from matplotlib.colors import LogNorm
from matplotlib.patches import Patch, Polygon, Rectangle
from matplotlib.ticker import StrMethodFormatter
from pyproj import Transformer

from analyses.helpers.publication import (
    AnalysisError,
    connect,
    image_table,
    table,
    text,
    unique_key,
)

CELL_SIZE_M = 100_000
LAND_COLOR = "#eeeeee"
ZERO_COLOR = "#e7298a"


def validated_grid(settings):
    """Aggregate VALID images into a fixed EPSG:8857 grid anchored at (0, 0).

    Positions are the parsed coordinates the validation table was checked with,
    not a second parse of the raw image fields.
    """
    with connect(settings) as connection:
        images = image_table(connection, settings)
        coordinates = table(
            connection,
            settings,
            "coordinates",
            ("source_id", "validation_status", "latitude", "longitude"),
        )
        taxonomy = table(
            connection,
            settings,
            "taxonomy",
            (
                "img_id",
                "update_status",
                "accepted_species_name",
                "accepted_rank",
                "accepted_name",
            ),
        )
        unique_key(connection, coordinates, "source_id")
        unique_key(connection, taxonomy, "img_id")
        records = connection.execute(f"""
            SELECT i.img_id, try_cast(c.longitude AS DOUBLE) AS longitude,
                try_cast(c.latitude AS DOUBLE) AS latitude,
                CASE WHEN t.update_status = 'MATCHED' THEN
                    coalesce({text("t.accepted_species_name")},
                        CASE WHEN lower(t.accepted_rank) = 'species'
                            THEN {text("t.accepted_name")} END) END AS species
            FROM {images} i
            JOIN {coordinates} c ON i.img_id = c.source_id
            LEFT JOIN {taxonomy} t USING (img_id)
            WHERE c.validation_status = 'VALID'
        """).df()
    if records.empty:
        raise AnalysisError("No images with VALID coordinates are available for the grid maps.")
    valid = (
        np.isfinite(records.longitude)
        & np.isfinite(records.latitude)
        & records.longitude.between(-180, 180)
        & records.latitude.between(-90, 90)
        & ~((records.longitude == 0) & (records.latitude == 0))
    )
    if not valid.all():
        raise AnalysisError("Images marked VALID contain unusable coordinates; refresh validation.")
    projection = Transformer.from_crs("EPSG:4326", "EPSG:8857", always_xy=True)
    # Canonicalize the antimeridian so +180 and -180 occupy the same cell.
    longitude = (records.longitude.to_numpy() + 180) % 360 - 180
    x, y = projection.transform(longitude, records.latitude.to_numpy())
    records["grid_x"] = np.floor(np.asarray(x) / CELL_SIZE_M).astype(int)
    records["grid_y"] = np.floor(np.asarray(y) / CELL_SIZE_M).astype(int)
    grid = records.groupby(["grid_x", "grid_y"], as_index=False).agg(
        image_count=("img_id", "size"),
        species_count=("species", "nunique"),
        identified_image_count=("species", "count"),
    )
    grid["x_min_m"] = grid.grid_x * CELL_SIZE_M
    grid["y_min_m"] = grid.grid_y * CELL_SIZE_M
    grid["cell_area_km2"] = 10_000
    grid["crs"] = "EPSG:8857"
    return grid


def grid_map(ax, grid, root, column="species_count", title="Species diversity"):
    """Draw one grid panel on an existing axes and return its color mappable."""
    projection = Transformer.from_crs("EPSG:4326", "EPSG:8857", always_xy=True)
    features = json.loads((root / "analyses/data/ne_110m_admin_0_countries.geojson").read_text())[
        "features"
    ]
    outlines = []
    for feature in features:
        geometry = feature["geometry"]
        if geometry is None:
            continue
        polygons = (
            geometry["coordinates"]
            if geometry["type"] == "MultiPolygon"
            else [geometry["coordinates"]]
        )
        for polygon in polygons:
            x, y = projection.transform(*zip(*polygon[0]))
            outlines.append(Polygon(np.column_stack((x, y))))
    ax.add_collection(
        PatchCollection(
            outlines,
            facecolor=LAND_COLOR,
            edgecolor="#bbbbbb",
            linewidth=0.3,
        )
    )
    cells = [Rectangle((r.x_min_m, r.y_min_m), CELL_SIZE_M, CELL_SIZE_M) for r in grid.itertuples()]
    values = grid[column].to_numpy()
    # Cell counts are heavily right-skewed, so a linear scale renders nearly every
    # cell in the lowest colour. A log scale needs a positive floor: occupied cells
    # with zero accepted species are masked and drawn in a separate colour.
    cmap = colormaps["viridis"].with_extremes(bad=ZERO_COLOR)
    collection = PatchCollection(
        cells,
        cmap=cmap,
        norm=LogNorm(1, max(int(values.max()), 2)),
        edgecolor="none",
        rasterized=True,
    )
    collection.set_array(np.ma.masked_less(values, 1))
    ax.add_collection(collection)
    width = projection.transform(180, 0)[0]
    height = projection.transform(0, 90)[1]
    ax.set(
        xlim=(-width - CELL_SIZE_M, width + CELL_SIZE_M),
        ylim=(-height - CELL_SIZE_M, height + CELL_SIZE_M),
        aspect="equal",
    )
    ax.set_axis_off()
    ax.set_title(title, loc="left")
    return collection


def plain_log_ticks(colorbar):
    """Label a horizontal log colorbar with plain counts rather than powers of ten."""
    colorbar.ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    return colorbar


def grid_legend(ax, grid, column):
    """Explain occupied cells that carry no value, and draw nothing when none do.

    Bare land needs no entry: a map of where images are implies that the rest of
    the world has none. A cell drawn outside the colour scale does need one.
    """
    if not (grid[column] < 1).any():
        return
    ax.legend(
        handles=[Patch(facecolor=ZERO_COLOR, label="Validated images, no accepted species")],
        loc="lower left",
        fontsize=8,
        frameon=False,
    )
