"""The image occurrence table bundled as a supplementary file for publication.

One row per image in the filtered image_meta view, joined one-to-one to its
harmonized taxonomy, locality, coordinate validation, provenance, institution
directory entry, and GBIF occurrence record. DuckDB writes the files directly,
so the source database stays read-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml
from dotenv import dotenv_values

from analyses.helpers.publication import (
    AnalysisError,
    Settings,
    connect,
    image_table,
    project_root,
    table,
    text,
    unique_key,
)

GADM_URL = "https://gadm.org/download_world.html"


@dataclass(frozen=True)
class Column:
    name: str
    expression: str
    description: str


# MATCHED records only, as in the figures: subspecies roll up to their species,
# and genus-only or ambiguous matches have no species.
ACCEPTED_SPECIES = """CASE WHEN t.update_status = 'MATCHED' THEN coalesce(
    nullif(trim(t.accepted_species_name), ''),
    CASE WHEN lower(t.accepted_rank) = 'species' THEN nullif(trim(t.accepted_name), '') END
) END"""

COLUMNS = (
    Column(
        "specimenID",
        text("i.uuid"),
        "Occurrence identifier of the specimen (GBIF occurrenceID or the aggregator's "
        "record ID). The dorsal and ventral images of one specimen share it.",
    ),
    Column(
        "species",
        ACCEPTED_SPECIES,
        "Accepted species in the Catalogue of Life. Subspecies are grouped under their "
        "species. Empty when the name matched only a genus, was ambiguous, or did not match.",
    ),
    Column(
        "sourceDB",
        "lower(" + text("i.source_db") + ")",
        "Aggregator the image came from (gbif, scanbugs, ecdysis); records carried by "
        "several aggregators keep a combined key such as gbif/scanbugs.",
    ),
    Column("sex", "lower(" + text("i.sex") + ")", "Sex as recorded, lowercased."),
    Column(
        "institution",
        "coalesce(" + text("d.name") + ", " + text("p.institution_code") + ")",
        "Institution holding the specimen, by its GRSciColl or publisher name; the "
        "institution code when no name was resolved.",
    ),
    Column("URI", text("i.uri"), "URI of the original image file."),
    Column(
        "imageID",
        "i.img_id",
        "BioCosmos image identifier that keys the image embeddings and the website.",
    ),
    Column(
        "view",
        "lower(" + text("i.class_dv") + ")",
        "Dorsal or ventral, predicted by the view classifier in Lürig et al., 2025: https://doi.org/10.1111/ele.14495.",
    ),
    Column("viewConfidence", "i.confidence_dv", "Classifier probability of the view."),
    Column("imageWidth", "i.width", "Width in pixels of the segmented specimen."),
    Column("imageHeight", "i.height", "Height in pixels of the segmented specimen."),
    Column("license", text("i.license"), "License of the image."),
    Column("rightsHolder", text('g."rightsHolder"'), "Rights holder of the GBIF record."),
    Column("gbifID", 'g."gbifID"', "GBIF occurrence key."),
    Column(
        "datasetKey",
        text('g."datasetKey"'),
        "GBIF dataset key used for a GBIF derived dataset.",
    ),
    Column("institutionCode", text("p.institution_code"), "Institution code."),
    Column("catalogNumber", text("p.catalog_number"), "Catalog number of the specimen."),
    Column("basisOfRecord", text('g."basisOfRecord"'), "Darwin Core basis of record."),
    Column("lifeStage", "lower(" + text("i.life_stage") + ")", "Life stage as recorded."),
    Column(
        "verbatimScientificName",
        text("t.recorded_name"),
        "Name as recorded by the source, before harmonization.",
    ),
    Column(
        "acceptedScientificName",
        text("t.accepted_name"),
        "Accepted name of the matched Catalogue of Life usage, at its own rank.",
    ),
    Column("acceptedNameAuthorship", text("t.accepted_authorship"), "Authorship."),
    Column("acceptedRank", "lower(" + text("t.accepted_rank") + ")", "Rank of the accepted name."),
    Column("colTaxonID", text("t.accepted_id"), "Catalogue of Life identifier of the name."),
    Column("family", text("t.accepted_family"), "Accepted family in the Catalogue of Life."),
    Column(
        "taxonMatchStatus",
        text("t.update_status"),
        "Outcome of matching to the Catalogue of Life: MATCHED, AMBIGUOUS, or UNMATCHED.",
    ),
    Column("taxonMatchMethod", text("t.match_method"), "How the name was matched."),
    Column("countryCode", "upper(" + text("l.country_code") + ")", "ISO 3166-1 alpha-2 code."),
    Column("country", text("l.country"), "Country as recorded."),
    Column("stateProvince", text("l.state_province"), "First-level division as recorded."),
    Column("county", text("l.county"), "Second-level division as recorded."),
    Column(
        "locality",
        "coalesce(" + text("l.locality") + ", " + text("l.verbatim_locality") + ")",
        "Recorded locality, falling back to the verbatim locality.",
    ),
    Column("decimalLatitude", "i.lat", "Recorded latitude, WGS84."),
    Column("decimalLongitude", "i.lon", "Recorded longitude, WGS84."),
    Column(
        "coordinateValidation",
        text("c.validation_status"),
        "Validation of the coordinates against GADM (geoharmonize): VALID, ADM1_MISMATCH, "
        "COUNTRY_MISMATCH, NO_REFERENCE_MATCH, MISSING_COORDINATE, or ZERO_COORDINATE.",
    ),
    Column("eventDate", text('g."eventDate"'), "Collection date as recorded by GBIF."),
    Column("year", 'g."year"', "Collection year."),
    Column("recordedBy", text('g."recordedBy"'), "Collector."),
)

OUTPUT_NAME = "image_occurrences"


def column_dictionary(columns: tuple[Column, ...] = COLUMNS) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "column": [column.name for column in columns],
            "description": [column.description for column in columns],
        }
    )


def occurrence_query(connection, settings: Settings, columns: tuple[Column, ...]) -> str:
    """One row per image; every join is checked to be one-to-one."""

    images = image_table(
        connection,
        settings,
        ("uuid", "uri", "source_db", "sex", "class_dv", "confidence_dv", "license"),
    )
    taxonomy = table(connection, settings, "taxonomy", ("img_id", "update_status"))
    locality = table(connection, settings, "locality", ("img_id", "locality"))
    coordinates = table(connection, settings, "coordinates", ("source_id", "validation_status"))
    provenance = table(connection, settings, "provenance", ("img_id", "institution_code"))
    institutions = table(connection, settings, "institutions", ("code", "name"))
    gbif = table(connection, settings, "gbif", ("occurrenceID", "gbifID"))

    for identifier, key in (
        (taxonomy, "img_id"),
        (locality, "img_id"),
        (coordinates, "source_id"),
        (provenance, "img_id"),
        (institutions, "code"),
    ):
        unique_key(connection, identifier, key)

    selected = ",\n    ".join(f'{column.expression} AS "{column.name}"' for column in columns)

    # gbif_meta repeats a few occurrenceIDs. Keep the most complete row, tie-broken
    # by gbifID, the same choice the backend's provenance table makes.
    return f"""
WITH gbif AS (
    SELECT * FROM {gbif}
    WHERE {text('"occurrenceID"')} IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY {text('"occurrenceID"')}
        ORDER BY ({text('"institutionCode"')} IS NULL), ({text('"catalogNumber"')} IS NULL),
            "gbifID"
    ) = 1
)
SELECT
    {selected}
FROM {images} AS i
LEFT JOIN {taxonomy} AS t ON t.img_id = i.img_id
LEFT JOIN {locality} AS l ON l.img_id = i.img_id
LEFT JOIN {coordinates} AS c ON c.source_id = i.img_id
LEFT JOIN {provenance} AS p ON p.img_id = i.img_id
LEFT JOIN {institutions} AS d ON d.code = p.institution_code
LEFT JOIN gbif AS g ON {text('g."occurrenceID"')} = {text("i.uuid")}
ORDER BY "species" NULLS LAST, "specimenID", "imageID"
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)

    return digest.hexdigest()


def col_release(root: Path) -> dict:
    """The Catalogue of Life release the backend ingested, from its ColDP metadata.yaml."""

    backend = root / "backend"
    env = {**dotenv_values(backend / ".env"), **os.environ}
    directory = env.get("COL_DIR")

    if not directory:
        raise AnalysisError("Set COL_DIR in backend/.env to the ingested ColDP release.")

    directory = Path(directory).expanduser()

    if not directory.is_absolute():
        directory = backend / directory

    metadata = directory / "metadata.yaml"

    if not metadata.is_file():
        raise AnalysisError(f"No ColDP metadata.yaml in {directory}.")

    with metadata.open() as handle:
        release = yaml.safe_load(handle)

    doi = release.get("doi")

    return {
        "title": release.get("title"),
        "alias": release.get("alias"),
        "version": release.get("version"),
        "issued": str(release.get("issued")),
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else None,
        "checklistbank": f"https://www.checklistbank.org/dataset/{release['key']}"
        if release.get("key")
        else None,
    }


def gadm_release(connection, settings: Settings, root: Path) -> dict:
    """The GADM layer the coordinates were validated against, from the geoharmonize run."""

    coordinates = table(connection, settings, "coordinates", ("run_id", "gadm_sha256"))
    runs = connection.execute(f"SELECT DISTINCT run_id, gadm_sha256 FROM {coordinates}").fetchall()

    if len(runs) != 1:
        raise AnalysisError(f"{coordinates} mixes {len(runs)} geoharmonize runs; expected one.")

    run_id, checksum = runs[0]
    release = {"version": None, "layer": None, "file": None, "sha256": checksum}
    report = root / "reports/geography" / run_id / "coordinate_run.json"

    # The run report is gitignored; without it only the checksum identifies the file.
    if report.is_file():
        run = json.loads(report.read_text())
        source = Path(run["gadm_source"]).name
        # gadm_410-levels.gpkg is GADM 4.1; gadm36 is 3.6.
        version = re.search(r"gadm_?(\d)(\d)", source)
        release |= {
            "version": f"{version[1]}.{version[2]}" if version else None,
            "layer": run.get("gadm_layer"),
            "file": source,
        }

    return {**release, "url": GADM_URL}


def export_occurrences(
    settings: Settings,
    columns: tuple[Column, ...] = COLUMNS,
    name: str = OUTPUT_NAME,
) -> dict[str, Path]:
    """Write the table as Parquet and gzipped CSV, with its column dictionary and manifest."""

    root = project_root(settings.output)
    col = col_release(root)
    settings.output.mkdir(parents=True, exist_ok=True)
    paths = {
        "parquet": settings.output / f"{name}.parquet",
        "csv": settings.output / f"{name}.csv.gz",
        "columns": settings.output / f"{name}_columns.csv",
        "manifest": settings.output / f"{name}_manifest.json",
    }

    with connect(settings) as connection:
        query = occurrence_query(connection, settings, columns)
        (images,) = connection.execute(
            f"SELECT count(*) FROM {settings.tables['images']}"
        ).fetchone()
        rows, specimens, species = connection.execute(
            f'SELECT count(*), count(DISTINCT "specimenID"), count(DISTINCT "species") '
            f"FROM ({query})"
        ).fetchone()

        if rows != images:
            raise AnalysisError(f"The export has {rows:,} rows for {images:,} images.")

        connection.execute(
            f"COPY ({query}) TO '{paths['parquet']}' (FORMAT parquet, COMPRESSION zstd)"
        )
        connection.execute(
            f"COPY ({query}) TO '{paths['csv']}' (FORMAT csv, HEADER, COMPRESSION gzip)"
        )
        taxonomy_state = connection.execute(
            "SELECT fingerprint, loaded_at FROM ingestion_state "
            "WHERE source_key = 'col_taxonomy_update'"
        ).fetchone()
        gadm = gadm_release(connection, settings, root)

    column_dictionary(columns).to_csv(paths["columns"], index=False)
    manifest = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "database": settings.database.name,
        "catalogue_of_life": col,
        "gadm": gadm,
        "excluded_families": list(settings.exclude_families),
        "taxonomy_update": (
            {"fingerprint": taxonomy_state[0], "loaded_at": str(taxonomy_state[1])}
            if taxonomy_state
            else None
        ),
        "rows": rows,
        "specimens": specimens,
        "species": species,
        "columns": [column.name for column in columns],
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for key, path in paths.items()
            if key != "manifest"
        },
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n")

    return paths
