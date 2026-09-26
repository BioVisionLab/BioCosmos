"""Read-only summaries and panels for the morphospace publication figure.

Reads the tables `morphospace integrate` wrote into the backend database
(packages/morphospace). Nothing here recomputes the morphospaces: the figure
shows exactly what the site serves, from one identified run.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.path import Path as MarkerPath
from PIL import Image

from analyses.helpers.publication import (
    AnalysisError,
    Settings,
    connect,
    project_root,
    table,
)

SIDES = ("dorsal", "ventral")
# The site's light-theme morphospace tokens (`--ms-*` in
# src/components/morphospace/morphospace.css): ColorBrewer Dark2 slots 1 and 2
# for the sides, drawn on a white card.
SIDE_COLORS = {"dorsal": "#1b9e77", "ventral": "#d95f02"}
SURFACE = "#ffffff"
GRID_COLOR = "#ece8e8"
AXIS_COLOR = "#534646"
# deep-mocha-600, -200 and -50 (src/app/globals.css): the site's muted text and
# the border and fill of its representative-image frames.
MUTED_TEXT = "#6f5d5d"
FRAME_EDGE = "#d1c7c7"
FRAME_FILL = "#f3f1f1"
# Panel A's groups (families, or genera inside a family): ColorBrewer Dark2 in
# order, each with its own marker so no group depends on color alone. Groups
# past the palette are drawn in `OTHER_COLOR`.
GROUP_COLORS = ("#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#a6761d")
GROUP_MARKERS = ("o", "s", "^", "D", "v", "P")
OTHER_COLOR = "#bdbdbd"
# A group mean's marker size, and the share of its width the white center of a
# hollow (ventral) mean takes.
MEAN_SIZE = 200
HOLLOW_SCALE = 0.52
# A triangle's is smaller: at the circle's share its band is visibly thinner,
# and at the circle's band thickness the white all but disappears.
TRIANGLE_HOLLOW_SCALE = 0.42
# The vertices matplotlib draws `^` and `v` from, centered on their bounding
# box rather than on the triangle.
TRIANGLE_VERTICES = {
    "^": np.array([[0.0, 1.0], [-1.0, -1.0], [1.0, -1.0]]),
    "v": np.array([[0.0, -1.0], [-1.0, 1.0], [1.0, 1.0]]),
}
# Points shrink and thin out past this many, as on the site.
DENSE = 2000
# Outer side of the square frame around each axis-end image, and the padding
# between the frame and the image inside it, in points.
AXIS_IMAGE = 62
FRAME_PAD = 2
ANNOTATION_SIZE = 12
# The morphospace grid: a column for the y-axis ends, panel A, panel B; and a
# row for both plots over one for panel A's x-axis ends. Sharing the rows keeps
# panel B's plot level with panel A's.
PANEL_COLUMNS = (0.3, 1.25, 1)
# Height the x-axis ends need, and roughly what the plots' titles, legends and
# axis labels take from the rest, in inches.
X_STRIP_HEIGHT = (AXIS_IMAGE + 10) / 72
PANEL_DECORATIONS = 2.0


def morphospace_summaries(
    settings: Settings,
    *,
    scope_rank: str = "all",
    scope_key: str = "all",
) -> dict[str, pd.DataFrame]:
    """Every table the figure draws, one per panel plus the scope it is set in."""
    with connect(settings) as connection:
        scopes = table(
            connection,
            settings,
            "morphospace_scope",
            (
                "scope_rank",
                "scope_key",
                "scope_name",
                "parent_family",
                "n_species",
                "n_species_both",
                "explained_pc1",
                "explained_pc2",
                "dv_mantel_n",
                "dv_mantel_r",
                "dv_mantel_p",
                "run_id",
            ),
        )
        points = table(
            connection,
            settings,
            "morphospace_points",
            (
                "scope_rank",
                "scope_key",
                "accepted_species",
                "genus_key",
                "family_key",
                "side",
                "pc1",
                "pc2",
            ),
        )
        disparity = table(
            connection,
            settings,
            "morphospace_disparity",
            (
                "scope_rank",
                "scope_key",
                "side",
                "n_species",
                "sum_var",
                "rarefied_mean",
                "rarefied_low",
                "rarefied_high",
                "rarefy_k",
            ),
        )
        images = table(connection, settings, "images", ("img_id", "uuid"))
        extremes = table(
            connection,
            settings,
            "morphospace_extremes",
            (
                "scope_rank",
                "scope_key",
                "axis",
                "end",
                "accepted_species",
                "side",
                "img_id",
                "value",
            ),
        )
        scope = connection.execute(
            f"SELECT * FROM {scopes} WHERE scope_rank = ? AND scope_key = ?",
            [scope_rank, scope_key],
        ).df()
        if scope.empty:
            raise AnalysisError(
                f"No morphospace for {scope_rank} {scope_key!r}; run morphospace integrate."
            )
        run_ids = connection.execute(f"SELECT DISTINCT run_id FROM {scopes}").fetchall()
        if len(run_ids) != 1:
            raise AnalysisError("The morphospace tables mix runs; integrate one run.")
        scope_points = connection.execute(
            f"""
            SELECT accepted_species, genus_key, family_key, side, pc1, pc2
            FROM {points} WHERE scope_rank = ? AND scope_key = ?
            ORDER BY accepted_species, side
            """,
            [scope_rank, scope_key],
        ).df()
        # The whole collection first, as the reference the families sit against.
        family_disparity = connection.execute(
            f"""
            SELECT s.scope_rank, s.scope_key AS family_key, s.scope_name AS family,
                   d.side, d.n_species, d.sum_var, d.rarefied_mean, d.rarefied_low,
                   d.rarefied_high, d.rarefy_k
            FROM {scopes} s JOIN {disparity} d USING (scope_rank, scope_key)
            WHERE s.scope_rank IN ('all', 'family')
            ORDER BY s.scope_rank, s.scope_name, d.side
            """
        ).df()
        # The occurrence ID identifies the photographed specimen; one image has one.
        axis_extremes = connection.execute(
            f"""SELECT e.axis, e."end", e.accepted_species, e.side, e.img_id, e.value,
                   i.uuid AS occurrence_id
            FROM {extremes} e
            LEFT JOIN (SELECT img_id, any_value(uuid) AS uuid FROM {images} GROUP BY img_id) i
                USING (img_id)
            WHERE e.scope_rank = ? AND e.scope_key = ? AND e.axis IN ('pc1', 'pc2')
            ORDER BY e.axis, e."end" """,
            [scope_rank, scope_key],
        ).df()
    axis_extremes["specimen_id"] = axis_extremes["occurrence_id"].map(specimen_id)
    return {
        "scope": scope,
        "points": scope_points,
        "disparity": family_disparity,
        "extremes": axis_extremes,
    }


def site_axes_style(ax) -> None:
    """The site's recessive grid, with axis lines, ticks and text in its axis color."""
    ax.grid(True, color=GRID_COLOR, linewidth=0.9)
    ax.set_axisbelow(True)
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
    for name in ("left", "bottom"):
        ax.spines[name].set_color(AXIS_COLOR)
        ax.spines[name].set_linewidth(0.9)
    ax.tick_params(colors=AXIS_COLOR, labelcolor=AXIS_COLOR, width=0.9)
    ax.xaxis.label.set_color(AXIS_COLOR)
    ax.yaxis.label.set_color(AXIS_COLOR)


def side_handle(side: str, *, whisker: bool = False) -> Line2D:
    """A legend key drawn like the site's marks: dorsal filled, ventral hollow."""
    color = SIDE_COLORS[side]
    return Line2D(
        [],
        [],
        marker="o",
        markersize=9,
        linestyle="-" if whisker else "",
        linewidth=2.2,
        color=color,
        markerfacecolor=color if side == "dorsal" or whisker else SURFACE,
        markeredgecolor=SURFACE if side == "dorsal" or whisker else color,
        markeredgewidth=1.2 if side == "dorsal" or whisker else 1.8,
        label=side.capitalize(),
    )


def group_styles(points: pd.DataFrame, group: str) -> dict[str, tuple[str, str]]:
    """Color and marker for each group, most species-rich first.

    Groups beyond the palette fold into `OTHER_COLOR` rather than reusing a
    color, since cycled colors could not be told apart.
    """
    counts = points.loc[points["side"] == "dorsal", group].dropna().value_counts()
    leaders = counts.index[: len(GROUP_COLORS)]
    return {str(key): (GROUP_COLORS[slot], GROUP_MARKERS[slot]) for slot, key in enumerate(leaders)}


def draw_group(ax, rows: pd.DataFrame, color: str, marker: str, *, size: float, alpha: float):
    """One group's points: dorsal filled, ventral hollow, both in the group's color."""
    for side in SIDES:
        subset = rows.loc[rows["side"] == side]
        filled = side == "dorsal"
        ax.scatter(
            subset["pc1"],
            subset["pc2"],
            s=size,
            marker=marker,
            facecolors=to_rgba(color, alpha) if filled else "none",
            edgecolors=to_rgba(SURFACE, alpha * 0.8) if filled else to_rgba(color, alpha),
            linewidths=0.3 if filled else 0.8,
            rasterized=True,
            zorder=3,
        )


def hollow_center(marker: str) -> tuple[str | MarkerStyle, float]:
    """The white center of a hollow mean, and its scatter size.

    A symmetric marker shrinks about its own center, which leaves an even ring.
    A triangle would shrink about its bounding-box center instead, leaving the
    band thick at the apex and thin along the base, so it is shrunk about its
    incenter, the point equally far from all three sides.
    """
    vertices = TRIANGLE_VERTICES.get(marker)
    if vertices is None:
        return marker, MEAN_SIZE * HOLLOW_SCALE**2
    # Each vertex weighted by the length of the side opposite it.
    opposite = np.linalg.norm(np.roll(vertices, -1, axis=0) - np.roll(vertices, 1, axis=0), axis=1)
    incenter = opposite @ vertices / opposite.sum()
    inset = TRIANGLE_HOLLOW_SCALE * (vertices - incenter) + incenter
    # Matplotlib scales a path marker by its largest coordinate without
    # recentering it, so the size is set to keep the inset in the outer
    # triangle's units.
    extent = float(np.abs(inset).max())
    path = MarkerPath(np.vstack([inset, inset[:1]]), closed=True)
    return MarkerStyle(path), MEAN_SIZE * extent**2


def draw_group_means(ax, rows: pd.DataFrame, color: str, marker: str) -> None:
    """A group's mean dorsal and mean ventral position, joined, drawn over its points."""
    means = pd.DataFrame(rows.groupby("side")[["pc1", "pc2"]].mean()).reindex(list(SIDES))
    if means.isna().to_numpy().any():
        return
    ax.plot(
        means["pc1"],
        means["pc2"],
        color=AXIS_COLOR,
        linewidth=3.4,
        solid_capstyle="round",
        zorder=5,
    )
    ax.plot(means["pc1"], means["pc2"], color=color, linewidth=1.8, zorder=6)
    for side in SIDES:
        # A dark outline keeps the mean readable over its own group's points.
        ax.scatter(
            means.loc[side, "pc1"],
            means.loc[side, "pc2"],
            s=MEAN_SIZE,
            marker=marker,
            facecolors=color,
            edgecolors=AXIS_COLOR,
            linewidths=1.4,
            zorder=7,
        )
        if side == "ventral":
            # Hollowed from inside the filled marker, so the colored ring
            # meets the outline with no white gap between them.
            center, size = hollow_center(marker)
            ax.scatter(
                means.loc[side, "pc1"],
                means.loc[side, "pc2"],
                s=size,
                marker=center,
                facecolors=SURFACE,
                edgecolors="none",
                zorder=8,
            )


def draw_points(ax, points: pd.DataFrame, group: str) -> dict[str, tuple[str, str]]:
    """Species centroids colored and shaped by group, dorsal filled and ventral hollow.

    Groups are drawn largest first, so the smaller ones stay visible on top,
    and each group's mean dorsal and ventral positions are marked and joined.
    Returns each drawn group's color and marker.
    """
    styles = group_styles(points, group)
    dense = len(points) > DENSE
    alpha = 0.55 if dense else 0.85
    size = 14 if dense else 30
    others = points.loc[~points[group].isin(list(styles))]
    if len(others):
        draw_group(ax, others, OTHER_COLOR, "o", size=size, alpha=alpha * 0.6)
    for key, (color, marker) in styles.items():
        draw_group(ax, points.loc[points[group] == key], color, marker, size=size, alpha=alpha)
    for key, (color, marker) in styles.items():
        draw_group_means(ax, points.loc[points[group] == key], color, marker)
    return styles


def legend_handle(label: str, color: str, marker: str, *, filled: bool = True) -> Line2D:
    return Line2D(
        [],
        [],
        marker=marker,
        markersize=9,
        linestyle="",
        markerfacecolor=color if filled else SURFACE,
        markeredgecolor=color,
        markeredgewidth=1.6,
        label=label,
    )


def fit_bounds(ax, points: pd.DataFrame) -> None:
    """Fit both axes to the points with the site's 5% margin."""
    for column, setter in (("pc1", ax.set_xlim), ("pc2", ax.set_ylim)):
        values = points[column].to_numpy(dtype=float)
        low, high = float(values.min()), float(values.max())
        pad = (high - low or 1.0) * 0.05
        setter(low - pad, high + pad)


def image_directory(root: Path) -> tuple[Path, str]:
    """The backend's processed image directory and file format."""
    config = yaml.safe_load((root / "backend/app/configs/config.yaml").read_text())["images"]
    directory = Path(config["processed_dir"])
    if not directory.is_absolute():
        directory = root / "backend" / directory
    return directory, str(config["format"])


def square_image(image_id: str, directory: Path, extension: str) -> np.ndarray:
    """A representative image centered on a transparent square, like the site's frame.

    The full processed image is preferred over the thumbnail, which is too small
    for print. Transparency is kept, so the background shows the frame's fill
    rather than turning black.
    """
    candidates = (
        directory / f"{image_id}.{extension}",
        directory / "thumbnails" / f"{image_id}_thumbnail.{extension}",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise AnalysisError(f"Missing axis example image {image_id} under {directory}.")
    with Image.open(path) as source:
        image = source.convert("RGBA")
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return np.asarray(canvas)


def framed_image(ax, pixels: np.ndarray, xy: tuple[float, float], alignment) -> None:
    """Place an image in a rounded frame of `AXIS_IMAGE` points, anchored in axes fraction."""
    artist = AnnotationBbox(
        OffsetImage(pixels, zoom=(AXIS_IMAGE - 2 * FRAME_PAD) / pixels.shape[1]),
        xy,
        xycoords="axes fraction",
        box_alignment=alignment,
        frameon=True,
        # The box style owns the padding (a `pad` argument would be overridden by
        # it); both it and the rounding scale with `fontsize`, so 1 makes them points.
        fontsize=1,
        bboxprops={
            "boxstyle": f"round,pad={FRAME_PAD},rounding_size=4",
            "facecolor": FRAME_FILL,
            "edgecolor": FRAME_EDGE,
            "linewidth": 0.8,
        },
        annotation_clip=False,
    )
    ax.add_artist(artist)


def specimen_id(occurrence_id: object) -> str | None:
    """A specimen's ID as printed: the occurrence ID, or the last segment of a URL one.

    Some sources publish occurrence IDs as resolvable URLs (Naturalis, Luomus)
    whose last path segment is the specimen's own ID, e.g. ZMA.INS.5147993;
    others publish the ID itself, e.g. MCZ:Ent:209250.
    """
    if not isinstance(occurrence_id, str) or not occurrence_id.strip():
        return None
    value = occurrence_id.strip()
    if value.startswith(("http://", "https://")):
        return value.rstrip("/").rsplit("/", 1)[-1]
    return value


def end_lines(
    label: str, row: pd.Series, *, split_species: bool = False
) -> tuple[tuple[str, dict], ...]:
    """The lines beside an axis-end image: which end, the species, its side, specimen ID.

    `split_species` puts the genus and the epithet on lines of their own, for
    the y axis, where each line has to fit in half the plot's height.
    """
    species = str(row["accepted_species"])
    names = species.split(" ", 1) if split_species else [species]
    italic = {"fontstyle": "italic", "color": AXIS_COLOR}
    lines = [
        (label, {"fontweight": "semibold", "color": AXIS_COLOR}),
        *((name, italic) for name in names),
        (f"({row['side']})", {"color": MUTED_TEXT}),
    ]
    identifier = row["specimen_id"]
    if isinstance(identifier, str):
        lines.append((identifier, {"color": MUTED_TEXT}))
    return tuple(lines)


def extreme_row(extremes: pd.DataFrame, axis: str, end: str) -> pd.Series:
    rows = extremes.loc[(extremes["axis"] == axis) & (extremes["end"] == end)]
    if len(rows) != 1:
        raise AnalysisError(
            f"Expected one {axis} {end} image example; integrate morphospace again."
        )
    return rows.iloc[0]


def y_axis_ends(strip, extremes: pd.DataFrame, directory: Path, extension: str) -> None:
    """The y axis's two ends beside it, as on the site: high at the top, low at the bottom.

    Each image sits flush with its end of the plot and its text runs bottom to
    top along the axis, starting against the image.
    """
    gap = AXIS_IMAGE + 8
    line = ANNOTATION_SIZE * 1.25
    for end, y, alignment, offset, va in (
        ("max", 1.0, (0.5, 1.0), -gap, "top"),
        ("min", 0.0, (0.5, 0.0), gap, "bottom"),
    ):
        row = extreme_row(extremes, "pc2", end)
        framed_image(
            strip, square_image(str(row["img_id"]), directory, extension), (0.5, y), alignment
        )
        label = f"{'High' if end == 'max' else 'Low'} PC2"
        lines = end_lines(label, row, split_species=True)
        for index, (text, style) in enumerate(lines):
            strip.annotate(
                text,
                (0.5, y),
                xycoords="axes fraction",
                xytext=((index - (len(lines) - 1) / 2) * line, offset),
                textcoords="offset points",
                rotation=90,
                ha="center",
                va=va,
                fontsize=ANNOTATION_SIZE,
                annotation_clip=False,
                **style,
            )


def x_axis_ends(strip, extremes: pd.DataFrame, directory: Path, extension: str) -> None:
    """The x axis's two ends below it, as on the site: low left, high right, text inside."""
    gap = AXIS_IMAGE + 10
    line = ANNOTATION_SIZE * 1.25
    for end, x, alignment, offset, ha in (
        ("min", 0.0, (0.0, 0.5), gap, "left"),
        ("max", 1.0, (1.0, 0.5), -gap, "right"),
    ):
        row = extreme_row(extremes, "pc1", end)
        framed_image(
            strip, square_image(str(row["img_id"]), directory, extension), (x, 0.5), alignment
        )
        label = f"{'High' if end == 'max' else 'Low'} PC1"
        lines = end_lines(label, row)
        for index, (text, style) in enumerate(lines):
            strip.annotate(
                text,
                (x, 0.5),
                xycoords="axes fraction",
                xytext=(offset, ((len(lines) - 1) / 2 - index) * line),
                textcoords="offset points",
                ha=ha,
                va="center",
                fontsize=ANNOTATION_SIZE,
                annotation_clip=False,
                **style,
            )


def place_y_strip(container, ax):
    """An axes for the y-axis ends, the plot's height, just left of the axis title.

    The site sets the ends outside the whole axis, title included, so the strip
    is placed from the laid-out extent of the tick labels and title rather than
    from the plot box. `container` is the figure or subfigure `ax` belongs to;
    axes positions are fractions of it.
    """
    renderer = container.canvas.get_renderer()
    axis_left = ax.yaxis.get_tightbbox(renderer).x0
    box = ax.get_position()
    dpi = container.canvas.figure.dpi
    width = (AXIS_IMAGE + 18) * dpi / 72
    gap = 6 * dpi / 72
    to_container = container.transSubfigure.inverted()
    left = to_container.transform((axis_left - gap - width, 0))[0]
    right = to_container.transform((axis_left - gap, 0))[0]
    strip = container.add_axes((left, box.y0, right - left, box.height))
    strip.set_axis_off()
    return strip


def morphospace_axes(container):
    """Axes for both morphospace panels, in a figure or subfigure with constrained layout.

    Returns panel A's plot, the strip below it for its x-axis ends, and panel
    B's plot. The empty first column keeps room for the y-axis ends, which
    `axis_ends` places once the layout is final.
    """
    # Constrained layout splits what the decorations leave by these ratios, so the
    # x-axis ends get the height their images need whatever the container's size.
    height = container.bbox.height / container.canvas.figure.dpi
    plot_height = max(height - PANEL_DECORATIONS - X_STRIP_HEIGHT, X_STRIP_HEIGHT)
    grid = container.add_gridspec(
        2, 3, width_ratios=PANEL_COLUMNS, height_ratios=(plot_height, X_STRIP_HEIGHT)
    )
    ax_a = container.add_subplot(grid[0, 1])
    x_strip = container.add_subplot(grid[1, 1])
    x_strip.set_axis_off()
    ax_b = container.add_subplot(grid[0, 2])
    return ax_a, x_strip, ax_b


def pca_axes(container):
    """Axes for panel A on its own, in a figure or subfigure with constrained layout.

    Returns the plot and the strip below it for its x-axis ends, laid out as in
    `morphospace_axes` without panel B's column.
    """
    height = container.bbox.height / container.canvas.figure.dpi
    plot_height = max(height - PANEL_DECORATIONS - X_STRIP_HEIGHT, X_STRIP_HEIGHT)
    grid = container.add_gridspec(
        2, 2, width_ratios=PANEL_COLUMNS[:2], height_ratios=(plot_height, X_STRIP_HEIGHT)
    )
    ax = container.add_subplot(grid[0, 1])
    x_strip = container.add_subplot(grid[1, 1])
    x_strip.set_axis_off()
    return ax, x_strip


def axis_ends(container, ax, x_strip, extremes: pd.DataFrame, root: Path | None = None):
    """Panel A's representative images at both ends of both axes.

    Call after the layout is resolved (``fig.canvas.draw()``) and frozen: the
    y-axis strip is placed from where the axis ended up. Returns that strip,
    whose left edge is where panel A's title belongs.
    """
    directory, extension = image_directory(project_root(root))
    y_strip = place_y_strip(container, ax)
    y_axis_ends(y_strip, extremes, directory, extension)
    x_axis_ends(x_strip, extremes, directory, extension)
    return y_strip


def morphospace_panel(ax, summaries: dict[str, pd.DataFrame]) -> None:
    """Panel A: species centroids on PC1 × PC2 by family (genus inside a family).

    The axis-end images are added by `axis_ends` once the layout is final.
    """
    scope = summaries["scope"].iloc[0]
    points = summaries["points"]
    group = "family_key" if scope["scope_rank"] == "all" else "genus_key"
    styles = draw_points(ax, points, group)
    fit_bounds(ax, points)
    ax.set_xlabel(f"PC1 ({scope['explained_pc1'] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({scope['explained_pc2'] * 100:.1f}%)")
    site_axes_style(ax)
    groups = [
        legend_handle(key.capitalize(), color, marker) for key, (color, marker) in styles.items()
    ]
    if not points[group].isin(list(styles)).to_numpy().all():
        groups.append(legend_handle("Other", OTHER_COLOR, "o"))
    # Groups above the plot; how to read the marks in its empty upper-right corner.
    ax.add_artist(
        ax.legend(
            handles=groups,
            loc="lower left",
            bbox_to_anchor=(0, 1.02),
            ncols=4,
            frameon=False,
            fontsize=14,
            # No border padding and a handle no wider than its marker, so the
            # first column's markers sit on the y-axis line.
            borderpad=0,
            borderaxespad=0,
            handlelength=0.7,
            handletextpad=0.5,
            columnspacing=1.4,
            labelspacing=0.4,
            labelcolor=AXIS_COLOR,
        )
    )
    mean_label = "Family mean" if group == "family_key" else "Genus mean"
    ax.legend(
        handles=[
            legend_handle("Dorsal", AXIS_COLOR, "o"),
            legend_handle("Ventral", AXIS_COLOR, "o", filled=False),
            Line2D(
                [],
                [],
                marker="o",
                markersize=11,
                markerfacecolor=MUTED_TEXT,
                markeredgecolor=AXIS_COLOR,
                color=AXIS_COLOR,
                linewidth=2,
                label=f"{mean_label}, dorsal–ventral",
            ),
        ],
        loc="upper right",
        frameon=False,
        fontsize=13,
        handletextpad=0.4,
        labelspacing=0.4,
        borderaxespad=0.5,
        labelcolor=AXIS_COLOR,
    )


def disparity_panel(ax, frame: pd.DataFrame) -> None:
    """Panel B: rarefied disparity of each side, dot (mean) and whisker (95% interval).

    One row per family under the whole collection, dorsal above ventral, drawn
    like the site's side-disparity chart; each whisker is labeled with the
    species count it is resampled from. A side with fewer species than the
    rarefaction size has no estimate and is marked N/A rather than zero.
    """
    if frame.empty:
        raise AnalysisError("No family disparity is available; run morphospace integrate.")
    ks = frame["rarefy_k"].dropna().unique()
    if len(ks) != 1:
        raise AnalysisError("Disparity was rarefied at more than one size; integrate one run.")
    rows = frame.drop_duplicates("family_key")["family"].tolist()
    position = {family: index for index, family in enumerate(rows)}
    limit = float(np.nanmax(frame["rarefied_high"].to_numpy(dtype=float))) * 1.12
    for side, offset in (("dorsal", -0.17), ("ventral", 0.17)):
        subset = frame.loc[frame["side"] == side]
        y = subset["family"].map(position).to_numpy() + offset
        estimated = subset["rarefied_mean"].notna().to_numpy()
        color = SIDE_COLORS[side]
        ax.hlines(
            y[estimated],
            subset.loc[estimated, "rarefied_low"],
            subset.loc[estimated, "rarefied_high"],
            color=color,
            linewidth=2.2,
            capstyle="round",
            zorder=2,
        )
        ax.scatter(
            subset.loc[estimated, "rarefied_mean"],
            y[estimated],
            s=70,
            color=color,
            edgecolors=SURFACE,
            linewidths=1.5,
            zorder=3,
        )
        for value, high, n, missing in zip(
            y, subset["rarefied_high"], subset["n_species"], ~estimated, strict=True
        ):
            ax.annotate(
                "N/A" if missing else f"{int(n):,} spp.",
                (0 if missing else high, value),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=12,
                color=MUTED_TEXT,
            )
    # Rule off the whole collection from the families beneath it.
    if (frame["scope_rank"] == "all").any():
        ax.axhline(0.5, color=FRAME_EDGE, linewidth=1)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, limit)
    ax.set_xlabel(f"Rarefied disparity (k = {int(ks[0])} species)")
    site_axes_style(ax)
    ax.grid(False, axis="y")
    ax.spines["left"].set_visible(False)
    ax.legend(
        handles=[side_handle(side, whisker=True) for side in SIDES],
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncols=2,
        frameon=False,
        fontsize=15,
        handletextpad=0.4,
        columnspacing=1.2,
        borderaxespad=0.2,
        labelcolor=MUTED_TEXT,
    )
