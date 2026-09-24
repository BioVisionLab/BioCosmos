"""The written locality of each occurrence, and its coordinate validation.

`image_meta` carries no locality columns — only `lat` and `lon`. The Darwin
Core locality fields live on `gbif_meta`, which joins to it on
`uuid = occurrenceID`. This module builds `image_meta_locality` out of that
join at startup, keyed on `img_id`, the same shape `image_meta_taxonomy` has.

The coordinate validation beside it is *not* built here. It is written offline
by `geoharmonize integrate` with the backend stopped, because DuckDB allows a
single writer. Everything that reads it treats it as optional.
"""

import logging
import unicodedata
import uuid
from collections.abc import Mapping, Sequence

import duckdb
import polars as pl
import pycountry

from ..configs.config import GbifConfig, ImageMetaConfig, LocalityConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState
from .metadata import COORDINATE_KEY_COLUMN

logger = logging.getLogger(__name__)

UPDATE_SOURCE_KEY = "image_meta_locality"

# Bumped whenever the shape of the locality table changes.
#
# Part of the fingerprint for the same reason STATUS_SCHEMA_VERSION is on the
# taxonomy update: a fingerprint describes the *inputs* and cannot speak for
# the shape of the output, so without this a table built by an older version
# would satisfy every other check and go unrepaired.
LOCALITY_SCHEMA_VERSION = 1

# Columns this version writes that an older one did not.
REQUIRED_LOCALITY_COLUMNS = ("country", "country_code", "verbatim_locality")

# gbif_meta column -> the name it takes on image_meta_locality. Darwin Core
# camelCase in, snake_case out, matching every other table in this database.
GBIF_COLUMN_FOR_FIELD = {
    "country_code": "countryCode",
    "state_province": "stateProvince",
    "county": "county",
    "municipality": "municipality",
    "locality": "locality",
    "verbatim_locality": "verbatimLocality",
}

# The ranks coarsest first: the order repeats are resolved in. The one-line
# form is written the other way round, finest rank first.
LOCALITY_RANK_ORDER = ("country", "stateProvince", "county", "municipality", "locality")

# Codes pycountry does not carry. XK is the user-assigned code for Kosovo,
# which GBIF uses; ZZ means "unknown" and is deliberately left unresolved.
SUPPLEMENTARY_COUNTRY_NAMES = {"XK": "Kosovo"}


def _clean(column: str) -> str:
    """SQL reading a locality column, with GBIF's placeholders as NULL.

    GBIF writes an absent value as a bracketed note rather than leaving it
    empty — '[no specific locality data]', '[no verbatim locality data]'. The
    bracket shape is matched rather than those two exact strings, because the
    wording varies by publisher and a new one would otherwise be rendered
    verbatim as if it were the name of a place.
    """
    return f"""
        CASE
            WHEN trim(coalesce({column}, '')) = '' THEN NULL
            WHEN trim({column}) LIKE '[%]' THEN NULL
            ELSE trim({column})
        END
    """


def country_name_frame() -> pl.DataFrame:
    """ISO 3166-1 alpha-2 -> the name to display.

    `common_name` where pycountry has one, because its `name` is the treaty
    form: "Bolivia, Plurinational State of", "Taiwan, Province of China",
    "Korea, Republic of". Those are correct and unreadable in a table cell.

    A registered frame rather than a scalar UDF: the lookup has 249 possible
    inputs and runs over 619,787 rows, and registering a function on the
    process-wide connection would reach past the lock every other call holds.
    """
    rows = [
        (country.alpha_2, getattr(country, "common_name", None) or country.name)
        for country in pycountry.countries
    ]
    rows.extend(SUPPLEMENTARY_COUNTRY_NAMES.items())
    return pl.DataFrame(rows, schema=["country_code", "country_name"], orient="row")


def _normalize_place(value: str | None) -> str:
    """A casefolded, unaccented, punctuation-free form, to spot repeats.

    Accents are stripped because publishers disagree about them within a
    single record: one GBIF occurrence carries stateProvince "Sao Paulo" and
    locality "São Paulo", which are the same place written twice.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if character.isalnum() and not unicodedata.combining(character)
    )


def locality_display(row: Mapping[str, object]) -> str | None:
    """The locality as one line, finest rank first, the way an address is written.

    locality, municipality, county, stateProvince, then country — the locality
    falling back to verbatimLocality when it is empty, because 165,046
    occurrences carry only the verbatim form. Every locality the site shows,
    from this panel to the map cards, runs from the lowest rank to the highest.
    Empty ranks are skipped, and a rank repeating a coarser one is dropped:
    publishers routinely set municipality and locality to the same string, and
    "Ouro Preto, Ouro Preto" reads as a bug rather than as a place. Repeats are
    resolved coarsest first, so the coarser rank's spelling is the one kept.

    None when nothing survives, so a caller can omit the row entirely.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for field in LOCALITY_RANK_ORDER:
        value = row.get(field)
        if field == "locality" and not value:
            value = row.get("verbatimLocality")
        if not isinstance(value, str) or not value.strip():
            continue
        key = _normalize_place(value)
        if not key or key in seen:
            continue
        seen.add(key)
        parts.append(value.strip())
    return ", ".join(reversed(parts)) if parts else None


class LocalityService:
    """Join the occurrence locality out of gbif_meta and index it per image."""

    def __init__(self, duckdb_client: DuckDBClient):
        config = LocalityConfig()
        self.skip = config.skip
        self.table = config.table
        self.image_meta_table = ImageMetaConfig().table
        self.gbif_table = GbifConfig().table
        self.db_client = duckdb_client

    def ensure(self) -> bool:
        """Rebuild if the result is missing or out of date.

        Returns True when the table was rebuilt. Never raises: a failure here
        leaves the API serving occurrences without a locality, and says so.
        """
        if self.skip:
            logger.info("Skipping locality build as per configuration.")
            return False
        if not self.db_client.table_exists(self.image_meta_table):
            logger.warning(
                f"No '{self.image_meta_table}' table to derive locality from; skipping."
            )
            return False
        if not self.db_client.table_exists(self.gbif_table):
            logger.warning(
                f"No '{self.gbif_table}' table, which is where the locality fields "
                "live; specimens will carry no locality."
            )
            return False

        fingerprint = self._source_fingerprint()
        state = IngestionState(self.db_client)
        if (
            state.is_current(UPDATE_SOURCE_KEY, fingerprint)
            and self._table_is_current()
        ):
            logger.info("Locality table is already current; skipping.")
            return False

        try:
            self._build()
        except (duckdb.Error, ValueError, OSError) as error:
            logger.error(f"Locality build failed: {error}")
            return False

        state.mark(UPDATE_SOURCE_KEY, fingerprint)
        logger.info(
            f"Locality table built; {self.count_with_country():,} occurrences have a country."
        )
        return True

    def _source_fingerprint(self) -> str:
        """A token that changes when the locality source changes.

        Deliberately coarse — row counts of both inputs, not a content hash.
        Hashing gbif_meta's seven locality columns across 2,078,671 rows costs
        more than the rebuild it exists to avoid, and neither table is edited
        in place: gbif ingestion is CREATE TABLE IF NOT EXISTS and image_meta
        is replaced wholesale. LOCALITY_SCHEMA_VERSION is the escape hatch for
        when the shape rather than the data changes.
        """
        occurrences = self.db_client.execute(
            f"SELECT count(*) FROM {self.image_meta_table}"
        ).fetchone()[0]
        gbif = self.db_client.execute(
            f"SELECT count(*) FROM {self.gbif_table}"
        ).fetchone()[0]
        return f"{occurrences}:{gbif}:v{LOCALITY_SCHEMA_VERSION}"

    def _table_is_current(self) -> bool:
        """Whether a usable table is loaded — present, and the right shape."""
        if not self.db_client.table_exists(self.table):
            return False
        stale = [
            column
            for column in REQUIRED_LOCALITY_COLUMNS
            if not self.db_client.column_exists(self.table, column)
        ]
        if stale:
            logger.info(
                f"'{self.table}' is missing {', '.join(stale)}; rebuilding the locality table."
            )
            return False
        return True

    def _build(self) -> None:
        clean = {
            field: _clean(f'gbif."{source}"')
            for field, source in GBIF_COLUMN_FOR_FIELD.items()
        }
        temp_name = f"temp_country_names_{uuid.uuid4().hex}"
        with self.db_client.lock:
            self.db_client.register(temp_name, country_name_frame())
            try:
                self.db_client.execute(
                    f"""
                    CREATE OR REPLACE TABLE {self.table} AS
                    WITH cleaned AS (
                        SELECT
                            nullif(trim(gbif."occurrenceID"), '') AS occurrence_id,
                            gbif."gbifID" AS gbif_id,
                            upper({clean["country_code"]}) AS country_code,
                            {clean["state_province"]} AS state_province,
                            {clean["county"]} AS county,
                            {clean["municipality"]} AS municipality,
                            {clean["locality"]} AS locality,
                            {clean["verbatim_locality"]} AS verbatim_locality
                        FROM {self.gbif_table} AS gbif
                        WHERE nullif(trim(gbif."occurrenceID"), '') IS NOT NULL
                    ),
                    -- gbif_meta holds 119 duplicate occurrenceID values. Without
                    -- this the join fans out and those specimens appear twice in
                    -- every search result. The most complete row wins, then the
                    -- lowest gbifID, so the choice is stable across rebuilds.
                    deduped AS (
                        SELECT * FROM cleaned
                        QUALIFY row_number() OVER (
                            PARTITION BY occurrence_id
                            ORDER BY (country_code IS NULL),
                                     (state_province IS NULL),
                                     (locality IS NULL),
                                     (county IS NULL),
                                     gbif_id
                        ) = 1
                    )
                    SELECT
                        occurrence.img_id,
                        -- The occurrence key the locality was resolved through,
                        -- kept so an unmatched row can be told from a matched
                        -- one that simply recorded nothing: roughly 7% of
                        -- image_meta is scanbugs or ecdysis and has no GBIF
                        -- record at all.
                        deduped.occurrence_id,
                        deduped.country_code,
                        names.country_name AS country,
                        deduped.state_province,
                        deduped.county,
                        deduped.municipality,
                        deduped.locality,
                        deduped.verbatim_locality,
                        -- Carried so this table alone is a sufficient input for
                        -- `geoharmonize integrate`, which needs the coordinate
                        -- beside the recorded country it is checked against.
                        occurrence.lat,
                        occurrence.lon
                    FROM {self.image_meta_table} AS occurrence
                    LEFT JOIN deduped
                           ON deduped.occurrence_id = nullif(trim(occurrence.uuid), '')
                    LEFT JOIN {temp_name} AS names
                           ON names.country_code = deduped.country_code
                    """
                )
            finally:
                self.db_client.unregister(temp_name)

        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS image_meta_locality_img_idx ON {self.table} (img_id)"
        )
        self._verify_row_count()

    def _verify_row_count(self) -> None:
        """Warn if the join changed the number of occurrence rows.

        A fan-out means one image matched several GBIF records, which would
        duplicate it in search results.
        """
        row = self.db_client.execute(
            f"""
            SELECT
                (SELECT count(*) FROM {self.image_meta_table}) AS occurrences,
                (SELECT count(*) FROM {self.table}) AS localities
            """
        ).fetchone()
        if row is not None and row[0] != row[1]:
            logger.warning(
                f"Locality table has {row[1]:,} rows for {row[0]:,} occurrences; "
                "the GBIF join is not one-to-one."
            )

    def count_with_country(self) -> int:
        row = self.db_client.execute(
            f"SELECT count(*) FROM {self.table} WHERE country IS NOT NULL"
        ).fetchone()
        return row[0] if row is not None else 0


# Read back per occurrence. Snake_case in the table, camelCase out, matching
# the nested `taxonomy` block the same endpoint already serves.
_LOCALITY_FIELDS = (
    ("country", "country"),
    ("country_code", "countryCode"),
    ("state_province", "stateProvince"),
    ("county", "county"),
    ("municipality", "municipality"),
    ("locality", "locality"),
    ("verbatim_locality", "verbatimLocality"),
)

_COORDINATE_FIELDS = (
    ("validation_status", "validationStatus"),
    ("coordinate_check", "coordinateCheck"),
    ("country_check", "countryCheck"),
    ("adm1_check", "adm1Check"),
    ("recorded_country", "recordedCountry"),
    ("recorded_adm1", "recordedAdm1"),
    ("reference_country", "referenceCountry"),
    ("reference_adm1", "referenceAdm1"),
    ("run_id", "runId"),
    ("gadm_sha256", "gadmSha256"),
)

# DuckDB binds every parameter of a prepared statement, so an id list has to
# be split rather than sent whole.
_LOOKUP_CHUNK = 1000


class _OccurrenceBlockReader:
    """Read one optional per-image block.

    `key_column` is the column holding the image id. It is not always
    `img_id`: `geoharmonize integrate` names its key after the logical field
    it was told to read, which is `source_id` whatever column fed it.
    """

    _table_present: bool | None = None

    def __init__(
        self,
        duckdb_client: DuckDBClient,
        table: str,
        fields: tuple[tuple[str, str], ...],
        key_column: str = "img_id",
    ):
        self.table = table
        self.fields = fields
        self.key_column = key_column
        self.db_client = duckdb_client
        # Resolved on first use and cached for this instance, which lives for
        # one request.
        self._table_present = None

    def available(self) -> bool:
        if self._table_present is None:
            self._table_present = self.db_client.table_exists(self.table)
        return self._table_present

    def _projection(self) -> str:
        return ", ".join(f'"{column}"' for column, _ in self.fields)

    def get_for_image(self, img_id: str) -> dict | None:
        """The block for one image, or None when there is nothing to show."""
        if not self.available():
            return None
        result = self.db_client.execute_prepared_to_pl(
            f"SELECT {self._projection()} FROM {self.table} "
            f'WHERE "{self.key_column}" = ? LIMIT 1',
            [img_id],
        )
        if result is None or result.is_empty():
            return None
        row = result.to_dicts()[0]
        payload = {alias: row.get(column) for column, alias in self.fields}
        if not any(value is not None for value in payload.values()):
            return None
        return payload

    def get_for_images(self, img_ids: Sequence[str]) -> dict[str, dict]:
        """The block for many images, keyed by img_id."""
        if not img_ids or not self.available():
            return {}
        found: dict[str, dict] = {}
        ids = list(img_ids)
        for start in range(0, len(ids), _LOOKUP_CHUNK):
            chunk = ids[start : start + _LOOKUP_CHUNK]
            placeholders = ", ".join(["?"] * len(chunk))
            result = self.db_client.execute_prepared_to_pl(
                f'SELECT "{self.key_column}" AS img_id, {self._projection()} '
                f'FROM {self.table} WHERE "{self.key_column}" IN ({placeholders})',
                chunk,
            )
            if result is None or result.is_empty():
                continue
            for row in result.to_dicts():
                payload = {alias: row.get(column) for column, alias in self.fields}
                if any(value is not None for value in payload.values()):
                    found[row["img_id"]] = payload
        return found


class OccurrenceLocality:
    """Read the written locality for one occurrence image."""

    def __init__(self, duckdb_client: DuckDBClient):
        self._reader = _OccurrenceBlockReader(
            duckdb_client, LocalityConfig().table, _LOCALITY_FIELDS
        )

    def get_for_image(self, img_id: str) -> dict | None:
        """The locality block, with a precomputed one-line form.

        `display` is built here rather than in the browser so the species
        panel, the specimen modal and the search table cannot disagree about
        how the ranks are joined.
        """
        payload = self._reader.get_for_image(img_id)
        if payload is None:
            return None
        return {"display": locality_display(payload), **payload}


class OccurrenceCoordinates:
    """Read the geoharmonize coordinate validation for one occurrence image.

    The table is written offline by `geoharmonize integrate`, with the backend
    stopped, and is simply absent until that has been run — so every method
    returns None rather than raising, exactly as the taxonomy reader does
    before a colharmonize run has been loaded.
    """

    def __init__(self, duckdb_client: DuckDBClient):
        # `geoharmonize integrate` keys its output on `source_id`, the logical
        # field name, not on whatever column fed it.
        self._reader = _OccurrenceBlockReader(
            duckdb_client,
            LocalityConfig().coordinates_table,
            _COORDINATE_FIELDS,
            key_column=COORDINATE_KEY_COLUMN,
        )

    def get_for_image(self, img_id: str) -> dict | None:
        return self._reader.get_for_image(img_id)
