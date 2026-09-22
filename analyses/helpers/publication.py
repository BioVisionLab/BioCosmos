"""Configuration, read-only summaries, and exports used by Jupyter notebooks to create manuscript figures.

No ingestion, harmonization, application startup, or source database writes occur here.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import yaml
from dotenv import dotenv_values
from harmonize_core.identifiers import (
    parse_table_identifier,
    qualified_name,
    quote_identifier,
)
from matplotlib.patches import Wedge


class AnalysisError(RuntimeError):
    """An analysis prerequisite is unavailable or would produce misleading counts."""


@dataclass(frozen=True)
class Settings:
    database: Path
    output: Path
    tables: dict[str, str]


def project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "backend/app/configs/config.yaml").is_file():
            return candidate
    raise AnalysisError("Run from the BioCosmos repository or pass its root explicitly.")


def load_settings(root: Path | None = None) -> Settings:
    root = project_root(root)
    backend = root / "backend"
    # Using .env of the backend so the database path is
    # consistent with the backend's environment.
    env = {**dotenv_values(backend / ".env"), **os.environ}
    with (backend / "app/configs/config.yaml").open() as handle:
        config = yaml.safe_load(handle)
    directory = env.get("DUCK_DIR")
    if not directory:
        raise AnalysisError("Set DUCK_DIR in backend/.env or the kernel environment.")
    directory = Path(directory).expanduser()
    if not directory.is_absolute():
        directory = backend / directory
    database = directory / config["db"]["duck"]["file"]
    output = Path(env.get("BIOCOSMOS_ANALYSES_OUTPUT", root / "analyses/results"))
    if not output.is_absolute():
        output = root / "analyses" / output
    if not output.resolve().is_relative_to((root / "analyses").resolve()):
        raise AnalysisError("Figure output must remain inside analyses/.")
    tables = {
        "images": config["image_metadata"]["table"],
        "gbif": config["gbif"]["table"],
        "locality": config["locality"]["table"],
        "coordinates": config["locality"]["coordinates_table"],
        "taxonomy": config["col"]["occurrence_status_table"],
        "matches": config["col"]["matches_table"],
    }
    return Settings(database.resolve(), output.resolve(), tables)


@contextmanager
def connect(settings: Settings):
    if not settings.database.is_file():
        raise AnalysisError(f"Database not found: {settings.database}")
    try:
        connection = duckdb.connect(str(settings.database), read_only=True)
    except duckdb.Error as error:
        raise AnalysisError(
            "Cannot open the analysis database read-only. If the backend holds its lock, "
            "stop the backend before running these notebooks, or set DUCK_DIR to an "
            "existing offline snapshot. The notebook will not stop services or copy a live DB."
        ) from error
    try:
        yield connection
    finally:
        connection.close()


def table(
    connection,
    settings: Settings,
    name: str,
    required: tuple[str, ...],
) -> str:
    identifier = qualified_name(parse_table_identifier(settings.tables[name]))
    try:
        columns = {row[0] for row in connection.execute(f"DESCRIBE {identifier}").fetchall()}
    except duckdb.Error as error:
        raise AnalysisError(
            f"Missing prepared table {identifier}. Prepare it outside the notebooks; "
            "the backend prepares metadata/locality/taxonomy and geoharmonize integrate "
            "prepares coordinate validation."
        ) from error
    missing = set(required) - columns
    if missing:
        raise AnalysisError(f"{identifier} is missing required columns: {sorted(missing)}")
    return identifier


def unique_key(connection, identifier: str, key: str) -> None:
    key = quote_identifier(key)
    total, distinct, missing = connection.execute(
        f"SELECT count(*), count(DISTINCT {key}), count(*) FILTER "
        f"(WHERE {key} IS NULL OR trim(cast({key} AS VARCHAR)) = '') FROM {identifier}"
    ).fetchone()
    if missing or total != distinct:
        raise AnalysisError(f"{identifier} must contain one nonblank row key per {key}.")


def text(column: str) -> str:
    return f"nullif(trim(cast({column} AS VARCHAR)), '')"


def counts(connection, query: str, population: str) -> pd.DataFrame:
    """Aggregate a query with one category per member of the stated population."""
    frame = connection.execute(
        f"SELECT category, count(*)::BIGINT AS count FROM ({query}) "
        "GROUP BY category ORDER BY count DESC, category"
    ).df()
    total = int(frame["count"].sum())
    if not total:
        raise AnalysisError(f"No {population} are available for this figure.")
    frame["percentage"] = frame["count"] * 100.0 / total
    frame["denominator"] = total
    frame["population"] = population
    return frame


def image_table(connection, settings: Settings, extra=()) -> str:
    identifier = table(connection, settings, "images", ("img_id", *extra))
    unique_key(connection, identifier, "img_id")
    return identifier


# How the recorded aggregator keys print. A record carried by several aggregators
# keeps its combined key rather than being counted under each one.
SOURCE_LABELS = {
    "gbif": "GBIF",
    "scanbugs": "SCAN",
    "ecdysis": "Ecdysis",
}


def source_label(value: str) -> str:
    """Render a recorded source_db key, including combined 'a/b' keys."""
    return " / ".join(
        SOURCE_LABELS.get(part.strip().lower(), part.strip().capitalize())
        for part in value.split("/")
    )


def dataset_summaries(settings: Settings) -> dict[str, pd.DataFrame]:
    with connect(settings) as connection:
        images = image_table(connection, settings, ("uuid", "class_dv", "source_db"))
        taxonomy = table(
            connection,
            settings,
            "taxonomy",
            (
                "img_id",
                "update_status",
                "accepted_family",
                "accepted_species_name",
                "accepted_rank",
                "accepted_name",
            ),
        )
        unique_key(connection, taxonomy, "img_id")
        joined = f"FROM {images} i LEFT JOIN {taxonomy} t USING (img_id)"
        family = counts(
            connection,
            f"""
            SELECT CASE WHEN t.update_status = 'MATCHED'
                THEN coalesce({text("t.accepted_family")}, 'Unresolved')
                ELSE 'Unresolved' END AS category {joined}
        """,
            "images",
        )
        species = counts(
            connection,
            f"""
            SELECT CASE WHEN t.update_status = 'MATCHED' THEN coalesce(
                {text("t.accepted_species_name")},
                CASE WHEN lower(t.accepted_rank) = 'species'
                    THEN {text("t.accepted_name")} END, 'Unresolved')
                ELSE 'Unresolved' END AS category {joined}
        """,
            "images",
        )
        views = counts(
            connection,
            f"""
            SELECT coalesce(lower({text("class_dv")}), 'Unknown') AS category FROM {images}
        """,
            "images",
        )
        sources = counts(
            connection,
            f"""
            SELECT coalesce({text("source_db")}, 'Unknown') AS category FROM {images}
        """,
            "images",
        )
        sources["category"] = sources["category"].map(source_label)
        institutions = institution_counts(connection, settings, images)
    return {
        "family": family,
        "views": views,
        "species": species,
        "sources": sources,
        "institutions": institutions,
    }


def institution_counts(connection, settings: Settings, images: str) -> pd.DataFrame:
    gbif = table(connection, settings, "gbif", ("occurrenceID",))
    columns = {row[0] for row in connection.execute(f"DESCRIBE {gbif}").fetchall()}
    if not {"institutionID", "institutionCode"} & columns:
        raise AnalysisError("GBIF requires institutionID or institutionCode for attribution.")
    institution_id = text('"institutionID"') if "institutionID" in columns else "NULL::VARCHAR"
    code = text('"institutionCode"') if "institutionCode" in columns else "NULL::VARCHAR"
    # Collapse repeated GBIF rows before joining images. A code-only row can be
    # associated with an ID only when that code maps to exactly one recorded ID.
    query = f"""
        WITH recorded AS (
            SELECT DISTINCT {text('"occurrenceID"')} AS occurrence_id,
                {institution_id} AS institution_id, {code} AS code FROM {gbif}
        ), code_ids AS (
            SELECT code, count(DISTINCT institution_id) AS n, min(institution_id) AS id
            FROM recorded WHERE code IS NOT NULL GROUP BY code
        ), resolved AS (
            SELECT r.occurrence_id,
                CASE WHEN r.institution_id IS NOT NULL THEN 'id:' || r.institution_id
                    WHEN c.n = 1 THEN 'id:' || c.id
                    WHEN c.n > 1 THEN 'conflict:'
                    WHEN r.code IS NOT NULL THEN 'code:' || r.code END AS institution_key,
                r.code
            FROM recorded r LEFT JOIN code_ids c USING (code)
        ), occurrence AS (
            SELECT occurrence_id,
                CASE WHEN count(DISTINCT institution_key) > 1
                    OR bool_or(institution_key = 'conflict:') THEN 'conflict:'
                    ELSE min(institution_key) END AS institution_key
            FROM resolved GROUP BY occurrence_id
        ), labels AS (
            SELECT institution_key, min(code) AS code FROM resolved GROUP BY institution_key
        )
        SELECT coalesce(o.institution_key, 'missing:') AS institution_key,
            CASE WHEN o.institution_key = 'conflict:' THEN 'Conflicting attribution'
                WHEN o.institution_key IS NULL THEN 'Unattributed'
                ELSE coalesce(l.code, substr(o.institution_key, 4)) END AS category,
            count(*)::BIGINT AS count
        FROM {images} i LEFT JOIN occurrence o ON {text("i.uuid")} = o.occurrence_id
        LEFT JOIN labels l USING (institution_key)
        GROUP BY o.institution_key, l.code ORDER BY count DESC, category, institution_key
    """
    frame = connection.execute(query).df()
    # Distinct institutions can share a code; keep them separate and make that
    # distinction visible rather than plotting indistinguishable labels.
    duplicate_labels = frame["category"].duplicated(keep=False)
    frame.loc[duplicate_labels, "category"] = (
        frame.loc[duplicate_labels, "category"]
        + " ["
        + frame.loc[duplicate_labels, "institution_key"].str.removeprefix("id:")
        + "]"
    )
    total = int(frame["count"].sum())
    if not total:
        raise AnalysisError("No images are available for institution attribution.")
    frame["percentage"] = frame["count"] * 100.0 / total
    frame["denominator"] = total
    frame["population"] = "images"
    return frame


def geography_summaries(
    settings: Settings,
) -> dict[str, pd.DataFrame]:
    with connect(settings) as connection:
        images = image_table(connection, settings, ("lat", "lon"))
        locality = table(
            connection,
            settings,
            "locality",
            ("img_id", "locality", "verbatim_locality"),
        )
        coordinates = table(
            connection,
            settings,
            "coordinates",
            ("source_id", "validation_status"),
        )
        unique_key(connection, locality, "img_id")
        unique_key(connection, coordinates, "source_id")
        available = counts(
            connection,
            f"""
            SELECT CASE WHEN isfinite(try_cast(lat AS DOUBLE))
                AND isfinite(try_cast(lon AS DOUBLE)) THEN 'With coordinate pair'
                ELSE 'Missing or unparseable pair' END AS category FROM {images}
        """,
            "images",
        )
        detailed = counts(
            connection,
            f"""
            SELECT CASE WHEN coalesce({text("l.locality")}, {text("l.verbatim_locality")})
                IS NOT NULL THEN 'Detailed locality available' ELSE 'No detailed locality' END
                AS category FROM {images} i LEFT JOIN {locality} l USING (img_id)
        """,
            "images",
        )
        validation = counts(
            connection,
            f"""
            SELECT coalesce({text("c.validation_status")}, 'NOT_EVALUATED') AS category
            FROM {images} i LEFT JOIN {coordinates} c ON i.img_id = c.source_id
        """,
            "images",
        )
    return {
        "coordinate_availability": available,
        "locality_availability": detailed,
        "coordinate_validation": validation,
    }


def taxonomy_summaries(settings: Settings) -> dict[str, pd.DataFrame]:
    with connect(settings) as connection:
        images = image_table(connection, settings)
        taxonomy = table(
            connection,
            settings,
            "taxonomy",
            (
                "img_id",
                "input_taxon_key",
                "update_status",
                "match_method",
            ),
        )
        matches = table(
            connection,
            settings,
            "matches",
            (
                "input_taxon_key",
                "update_status",
                "match_method",
            ),
        )
        unique_key(connection, taxonomy, "img_id")
        unique_key(connection, matches, "input_taxon_key")
        image_source = f"FROM {images} i LEFT JOIN {taxonomy} t USING (img_id)"
        taxon_source = f"""FROM (
            SELECT DISTINCT t.input_taxon_key FROM {images} i
            JOIN {taxonomy} t USING (img_id) WHERE {text("t.input_taxon_key")} IS NOT NULL
        ) k LEFT JOIN {matches} t USING (input_taxon_key)"""
        result = {}
        for unit, source, population in (
            ("images", image_source, "images"),
            ("taxa", taxon_source, "unique input taxa"),
        ):
            for metric, column in (
                ("status", "update_status"),
                ("method", "match_method"),
            ):
                result[f"{unit}_{metric}"] = counts(
                    connection,
                    f"SELECT coalesce({text('t.' + column)}, 'UNCLASSIFIED') AS category {source}",
                    population,
                )
    return result


DEFAULT_PALETTE = "Dark2"


def bar_color(palette: str = DEFAULT_PALETTE):
    return sns.color_palette(palette)[0]


def pie_colors(wedges: int, palette: str = DEFAULT_PALETTE) -> list:
    """Colour wedges by position, so every pie in the manuscript shares one sequence."""
    return sns.color_palette(palette, n_colors=max(wedges, 1))


RESIDUAL_COLORS = ("#999999", "#cccccc")


def display_label(label: str, keep_case: bool = False) -> str:
    """Format a plotted category as sentence case without identifier underscores.

    keep_case leaves a label exactly as recorded, for identifiers such as institution
    codes whose capitalization carries meaning.
    """
    return label if keep_case else label.replace("_", " ").capitalize()


def top_share(
    frame: pd.DataFrame,
    top: int,
    *,
    exclude: tuple[str, ...] = (),
    other: str = "Other",
    excluded: str = "Excluded",
) -> pd.DataFrame:
    """Collapse a ranking into its top categories and residual groups of one whole.

    Unlike a top-ten bar panel, a pie needs the full population: categories after
    the top are pooled as `other`, and excluded categories (unresolved or unattributed
    records) are pooled as `excluded`. Residual rows are flagged so they plot last.
    Percentages are recomputed from counts over the unchanged denominator.
    """
    ranked = frame.loc[~frame["category"].isin(exclude)].sort_values(
        ["count", "category"], ascending=[False, True]
    )
    rows = [(row.category, int(row.count), False) for row in ranked.head(top).itertuples()]
    for label, count in (
        (other, int(ranked.iloc[top:]["count"].sum())),
        (
            excluded,
            int(frame.loc[frame["category"].isin(exclude), "count"].sum()),
        ),
    ):
        if count:
            rows.append((label, count, True))
    result = pd.DataFrame(rows, columns=["category", "count", "residual"])
    total = int(frame["count"].sum())
    if int(result["count"].sum()) != total:
        raise AnalysisError("Collapsed shares must preserve the full population.")
    result["percentage"] = result["count"] * 100.0 / total
    result["denominator"] = total
    result["population"] = frame["population"].iloc[0]
    return result


def publication_style(palette: str = DEFAULT_PALETTE) -> None:
    sns.set_theme(
        style="ticks",
        context="paper",
        palette=palette,
        font_scale=1.1,
    )
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
        }
    )


def bar_plot(
    ax,
    frame: pd.DataFrame,
    title: str,
    *,
    top: int | None = None,
    exclude: tuple[str, ...] = (),
    italic: bool = False,
    proportion: bool = True,
    palette: str = DEFAULT_PALETTE,
    keep_case: bool = False,
):
    """Draw counts/proportions without renormalizing top-ten subsets."""
    selected = frame.loc[~frame["category"].isin(exclude)].sort_values(
        ["count", "category"], ascending=[False, True]
    )
    if top:
        selected = selected.head(top)
    excluded = int(frame.loc[frame["category"].isin(exclude), "count"].sum())
    metric = "percentage" if proportion else "count"
    labels = selected["category"].astype(str).tolist()
    # Bars are one category per row, so the axis labels carry the meaning and a
    # single colour keeps the panel from implying a grouping that is not there.
    ax.barh(
        range(len(selected)),
        selected[metric],
        color=bar_color(palette),
    )
    ax.set_yticks(
        range(len(selected)),
        [display_label(label, keep_case) for label in labels],
    )
    ax.invert_yaxis()
    if italic:
        plt.setp(ax.get_yticklabels(), fontstyle="italic")
    for i, row in enumerate(selected.itertuples()):
        ax.annotate(
            f"{row.count:,} ({row.percentage:.1f}%)",
            (getattr(row, metric), i),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
        )
    if selected.empty:
        ax.text(
            0.5,
            0.5,
            "No eligible records",
            transform=ax.transAxes,
            ha="center",
        )
    maximum = float(selected[metric].max()) if not selected.empty else 1
    ax.set_xlim(0, 100 if proportion else max(maximum * 1.5, 1))
    ax.set_xlabel(axis_label(frame, proportion))
    ax.set_title(
        panel_title(frame, title, exclude, excluded),
        loc="left",
        fontsize=11,
    )
    sns.despine(ax=ax)
    return ax


def pie_plot(
    ax,
    frame: pd.DataFrame,
    title: str,
    *,
    italic: bool = False,
    palette: str = DEFAULT_PALETTE,
    keep_case: bool = False,
):
    """Draw a complete population as proportions of one whole, largest share first.

    Rows flagged `residual` (see top_share) follow the ranked shares in gray, so a
    pooled "Other" never takes a palette colour that implies a single category.
    """
    residual = frame["residual"] if "residual" in frame else pd.Series(False, frame.index)
    ranked = frame.loc[~residual].sort_values(["count", "category"], ascending=[False, True])
    selected = pd.concat([ranked, frame.loc[residual]])
    labels = selected["category"].astype(str).tolist()
    if int(residual.sum()) > len(RESIDUAL_COLORS):
        raise ValueError(f"A pie supports at most {len(RESIDUAL_COLORS)} residual groups.")
    wedges, _ = ax.pie(
        selected["count"],
        colors=[
            *pie_colors(len(ranked), palette)[: len(ranked)],
            *RESIDUAL_COLORS,
        ][: len(labels)],
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    # A legend beside the pie, not labels around each wedge: small adjacent wedges
    # (e.g. a 99% match status) otherwise stack their labels on top of each other.
    # It sits to the right, where it fills the space an equal-aspect pie leaves in
    # its grid cell instead of adding height below the panel.
    legend = ax.legend(
        wedges,
        [
            f"{display_label(label, keep_case)}: {row.count:,} ({row.percentage:.1f}%)"
            for label, row in zip(labels, selected.itertuples(), strict=True)
        ],
        loc="center left",
        bbox_to_anchor=(0.98, 0.5),
        frameon=False,
        fontsize=9,
        handlelength=1,
        handleheight=1,
    )
    if italic:
        plt.setp(legend.get_texts(), fontstyle="italic")
    ax.set_aspect("equal")
    ax.set_title(panel_title(frame, title, (), 0), loc="left", fontsize=11)
    return ax


def category_plot(
    ax,
    frame: pd.DataFrame,
    title: str,
    *,
    kind: str = "auto",
    top: int | None = None,
    exclude: tuple[str, ...] = (),
    italic: bool = False,
    proportion: bool = True,
    palette: str = DEFAULT_PALETTE,
    keep_case: bool = False,
):
    """Draw a summary as a pie when it compares two classes and as bars otherwise.

    Pass kind="pie" for a whole-population panel that is worth reading as shares of one
    total even though it has more than two classes.
    """
    if kind not in {"auto", "bar", "pie"}:
        raise ValueError("kind must be 'auto', 'bar', or 'pie'.")
    ranked = bool(top or exclude)
    if kind == "pie" and ranked:
        raise ValueError("A pie must show its whole population; drop top and exclude.")
    if kind == "pie" or (kind == "auto" and not ranked and frame["category"].nunique() == 2):
        return pie_plot(
            ax,
            frame,
            title,
            italic=italic,
            palette=palette,
            keep_case=keep_case,
        )
    return bar_plot(
        ax,
        frame,
        title,
        top=top,
        exclude=exclude,
        italic=italic,
        proportion=proportion,
        palette=palette,
        keep_case=keep_case,
    )


def panel_left(ax) -> float:
    """The leftmost display coordinate a panel's own drawing reaches.

    A pie is measured from its circle, not the axes box it is centred in, so its
    title starts where the wedges do. A bar panel reaches left of its axes box by
    the width of its tick labels. Anything else, a map among them, is measured from
    its box, which an equal-aspect projection has already shrunk to the graphic.
    """
    box = ax.get_window_extent()
    wedges = [patch for patch in ax.patches if isinstance(patch, Wedge)]
    if wedges:
        return min(wedge.get_window_extent().x0 for wedge in wedges)
    labels = [label.get_window_extent().x0 for label in ax.get_yticklabels() if label.get_text()]
    return min(box.x0, *labels) if labels else box.x0


def align_panel_titles(axes) -> None:
    """Align panel titles flush with their column and on the first line of each row.

    Horizontally, a left-aligned title starts at the axes box, which sits right of a
    bar panel's tick labels and inside the box of an equal-aspect pie or map. Each
    title moves to the leftmost point its panel draws (see panel_left), and rows laid
    out on the same number of columns share one anchor per column, so a map under a
    ranking starts where the ranking starts rather than where its graphic happens to
    begin. Vertically, matplotlib grows a multi-line title upwards from the axes, so
    a panel carrying a subtitle line lifts its heading above a single-line neighbour;
    padding the shorter titles in a row with trailing blank lines puts every heading
    on one line. Call it after the layout is resolved (``fig.canvas.draw()``) and
    frozen, because it reads the positions that layout produced.
    """
    rows: dict[int, list] = {}
    columns: dict[tuple[int, int], float] = {}
    for ax in axes:
        figure = ax.get_figure()
        spec = ax.get_subplotspec()
        cell = spec.get_position(figure)
        # Group titles by the cell's top edge in display space, so axes that live
        # in different subfigures still compare on the same scale.
        top = round(figure.transSubfigure.transform((0, cell.y1))[1])
        rows.setdefault(top, []).append(ax)
        column = (spec.get_gridspec().ncols, spec.colspan.start)
        columns[column] = min(columns.get(column, float("inf")), panel_left(ax))
    for row in rows.values():
        lines = max(len(ax.get_title(loc="left").split("\n")) for ax in row)
        for ax in row:
            spec = ax.get_subplotspec()
            box = ax.get_window_extent()
            title = ax.get_title(loc="left")
            padding = "\n " * (lines - len(title.split("\n")))
            left = columns[(spec.get_gridspec().ncols, spec.colspan.start)]
            ax.set_title(
                title + padding,
                loc="left",
                fontsize=11,
                x=(left - box.x0) / box.width,
            )


def axis_label(frame: pd.DataFrame, proportion: bool) -> str:
    population = str(frame["population"].iloc[0])
    return f"Percentage of all {population} (%)" if proportion else f"Number of {population}"


def panel_title(
    frame: pd.DataFrame,
    title: str,
    exclude: tuple[str, ...],
    excluded: int,
) -> str:
    population = str(frame["population"].iloc[0])
    denominator = int(frame["denominator"].iloc[0])
    subtitle = f"N = {denominator:,} {population}"
    if exclude:
        subtitle += f"; Unresolved / unattributed excluded: {excluded:,}"
    return f"{title}\n{subtitle}"


def export_figure(
    figure,
    settings: Settings,
    name: str,
    summaries: dict[str, pd.DataFrame],
):
    if Path(name).name != name:
        raise ValueError("Figure names must be plain filenames without directories.")
    settings.output.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg", "png"):
        figure.savefig(
            settings.output / f"{name}.{extension}",
            dpi=300,
            bbox_inches="tight",
        )
    for key, frame in summaries.items():
        if Path(key).name != key:
            raise ValueError("Summary names must be plain filenames without directories.")
        frame.to_csv(settings.output / f"{name}_{key}.csv", index=False)


def benchmark_data(root: Path | None = None) -> pd.DataFrame:
    frame = pd.read_csv(project_root(root) / "analyses/data/indexing_benchmark.csv")
    required = {"index", "model", "avg_ms", "recall@10"}
    if not required.issubset(frame):
        raise AnalysisError(f"Benchmark CSV requires {sorted(required)}")
    # Preserve the existing figure's exclusion. The 'No Index (baseline)' series stays.
    return frame.loc[frame["index"] != "Flat (brute-force)"].copy()
