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
from harmonize_core.identifiers import parse_table_identifier, qualified_name, quote_identifier


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


def table(connection, settings: Settings, name: str, required: tuple[str, ...]) -> str:
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


def dataset_summaries(settings: Settings) -> dict[str, pd.DataFrame]:
    with connect(settings) as connection:
        images = image_table(connection, settings, ("uuid", "class_dv"))
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
        institutions = institution_counts(connection, settings, images)
    return {"family": family, "views": views, "species": species, "institutions": institutions}


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


def geography_summaries(settings: Settings) -> dict[str, pd.DataFrame]:
    with connect(settings) as connection:
        images = image_table(connection, settings, ("lat", "lon"))
        locality = table(
            connection, settings, "locality", ("img_id", "locality", "verbatim_locality")
        )
        coordinates = table(connection, settings, "coordinates", ("source_id", "validation_status"))
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
            for metric, column in (("status", "update_status"), ("method", "match_method")):
                result[f"{unit}_{metric}"] = counts(
                    connection,
                    f"SELECT coalesce({text('t.' + column)}, 'UNCLASSIFIED') AS category {source}",
                    population,
                )
    return result


def publication_style() -> None:
    sns.set_theme(style="ticks", context="paper", palette="colorblind", font_scale=1.1)
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
    palette = sns.color_palette("colorblind", n_colors=max(len(frame), 1))
    color_map = dict(zip(sorted(frame["category"].astype(str)), palette, strict=True))
    # Stable meanings across the image/taxon panels even if a category is absent.
    semantic_colors = {
        "MATCHED": "#009E73",
        "VALID": "#009E73",
        "AMBIGUOUS": "#E69F00",
        "UNMATCHED": "#D55E00",
        "UNCLASSIFIED": "#777777",
        "NOT_EVALUATED": "#777777",
        "Unknown": "#777777",
        "Unresolved": "#777777",
        "Unattributed": "#777777",
        "Conflicting attribution": "#E69F00",
        "EXACT_ACCEPTED": "#009E73",
        "EXACT_SYNONYM": "#0072B2",
        "EXACT_CANONICAL": "#56B4E9",
        "UNIQUE_FAMILY_EPITHET": "#CC79A7",
        "SPELLING_GENUS": "#8C564B",
        "SPELLING_EPITHET": "#332288",
        "FUZZY_TYPO": "#882255",
        "MISSING_COORDINATE": "#999999",
        "COORDINATE_OUT_OF_RANGE": "#D55E00",
        "ZERO_COORDINATE": "#882255",
        "NO_REFERENCE_MATCH": "#56B4E9",
        "AMBIGUOUS_REFERENCE": "#E69F00",
        "COUNTRY_MISMATCH": "#0072B2",
        "ADM1_MISMATCH": "#CC79A7",
        "With coordinate pair": "#009E73",
        "Missing or unparseable pair": "#999999",
        "Detailed locality available": "#009E73",
        "No detailed locality": "#999999",
        "dorsal": "#0072B2",
        "ventral": "#E69F00",
        "lateral": "#CC79A7",
    }
    color_map.update(semantic_colors)
    ax.barh(range(len(selected)), selected[metric], color=[color_map[label] for label in labels])
    display_labels = [
        label.replace("_", " ").capitalize()
        if label in semantic_colors and label.isupper()
        else label
        for label in labels
    ]
    ax.set_yticks(range(len(selected)), display_labels)
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
        ax.text(0.5, 0.5, "No eligible records", transform=ax.transAxes, ha="center")
    maximum = float(selected[metric].max()) if not selected.empty else 1
    ax.set_xlim(0, 100 if proportion else max(maximum * 1.5, 1))
    population = str(frame["population"].iloc[0])
    ax.set_xlabel(
        f"Percentage of all {population} (%)" if proportion else f"Number of {population}"
    )
    denominator = int(frame["denominator"].iloc[0])
    subtitle = f"N = {denominator:,} {population}"
    if exclude:
        subtitle += f"; unresolved / unattributed excluded: {excluded:,}"
    ax.set_title(f"{title}\n{subtitle}", loc="left", fontsize=11)
    sns.despine(ax=ax)
    return ax


def export_figure(figure, settings: Settings, name: str, summaries: dict[str, pd.DataFrame]):
    if Path(name).name != name:
        raise ValueError("Figure names must be plain filenames without directories.")
    settings.output.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg", "png"):
        figure.savefig(settings.output / f"{name}.{extension}", dpi=300, bbox_inches="tight")
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
