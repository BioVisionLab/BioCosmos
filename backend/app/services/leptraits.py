import logging

import duckdb
import polars as pl

from ..configs.config import ColConfig, ImageMetaConfig, LepTraitConfig
from ..database.duckdb import DuckDBClient
from ..database.ingestion_state import IngestionState
from ..database.model import LepTraitData

logger = logging.getLogger(__name__)


class LepTraits:
    def __init__(self, duckdb: DuckDBClient):
        """
        Initializes the LepTraits service.
        This service connects to the DuckDB database to fetch traits for lepidopteran species.
        The caller is responsible for managing the database connection lifecycle.
        """
        config = LepTraitConfig()
        self.path = config.path
        self.table = config.table
        self.index_table = config.index_table
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self):
        """
        Ingests the LepTraits consensus CSV data into the DuckDB database.
        """
        if self.skip_ingestion:
            logger.info("Skipping LepTraits data ingestion as per configuration.")
            return
        try:
            self.db_client.create_if_not_exists_csv(
                table_name=self.table, csv_path=self.path
            )
            entries: int | None = self.count_entries()
            if entries is not None:
                logger.info(f"LepTraits data ingested successfully from '{self.path}'.")
                logger.info(f"Total entries after ingestion: {entries}")
        except Exception as e:
            logger.error(f"Failed to ingest LepTraits data from '{self.path}': {e}")
            raise e

    def count_entries(self) -> int | None:
        """
        Count the number of entries in the lep_traits_consensus table.
        """
        try:
            query = "SELECT COUNT(*) AS total_rows FROM lep_traits_consensus"
            result = self.db_client.execute(query).fetchall()
            logger.info(
                f"Counted {result[0][0]} entries in lep_traits_consensus table."
            )
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Failed to count entries in lep_traits_consensus table: {e}")
            return None

    def get(self, species_name: str) -> dict:
        """
        Fetches traits for a given species from the lep_traits_consensus table.

        LepTraits names a species by its own concept, which is often not the
        name the page is filed under: the collection's "Anaea basilia" is
        LepTraits' "Memphis basilia". When the name has no row of its own, the
        trait index supplies the LepTraits name it resolved to, so the page
        shows the same traits the searches matched it on.

        :param species_name: The name of the species to fetch traits for.
        :return: The traits data for the species.
        """
        name = _normalized(species_name)
        result = self._rows_named(name)
        if result.is_empty():
            resolved = self._indexed_name(name)
            if resolved is not None and resolved != name:
                logger.info(f"LepTraits lists '{species_name}' as '{resolved}'.")
                result = self._rows_named(resolved)
        if result.is_empty():
            logger.warning(f"No traits found for species '{species_name}'.")
            return {}
        if len(result) > 1:
            logger.warning(
                f"Multiple entries found for species '{species_name}'. Returning the first entry."
            )
        traits_data = LepTraitData.from_data(result.to_dicts()[0])
        return traits_data.model_dump()

    def _rows_named(self, name: str) -> pl.DataFrame:
        return self.db_client.execute_prepared_to_pl(
            f'SELECT * FROM {self.table} WHERE lower("Species") = ?', [name]
        )

    def _indexed_name(self, name: str) -> str | None:
        """The LepTraits name the trait index resolved this species to.

        Matches the name as the collection records it (the page key) or as
        the accepted species the index is keyed on. None before the index is
        built, or when LepTraits has no entry for the species at all.
        """
        if not self.db_client.table_exists(self.index_table):
            return None
        image_meta = ImageMetaConfig().table
        result = self.db_client.execute_prepared_to_pl(
            f"""
            SELECT t.leptraits_name
            FROM {self.index_table} t
            JOIN {image_meta} o USING (img_id)
            WHERE lower(replace(o.species, ' ', '_')) = ? OR t.trait_species = ?
            GROUP BY t.leptraits_name
            ORDER BY count(*) DESC, t.leptraits_name
            LIMIT 1
            """,
            [name.replace(" ", "_"), name],
        )
        if result is None or result.is_empty():
            return None
        return result["leptraits_name"][0]


def _normalized(name: str) -> str:
    """Lower-case with single spaces, as the index stores names."""
    return " ".join(name.replace("_", " ").split()).lower()


# The per-occurrence trait index
# ------------------------------
#
# LepTraits names its rows by its own species concept, which is not always
# the collection's: a synonym, a genus the collection files the species under
# differently, or a spelling variant. Matching the two by string drops those
# species, and a species the collection records under several spellings only
# matches under one of them. So the index resolves each LepTraits name to the
# accepted binomial Catalogue of Life gives it and joins that to the accepted
# species colharmonize resolved each occurrence to. Every row then belongs to
# a valid species, and every image of that species carries its traits.
#
# Values are stored as the text a reader would type, so the text search can
# match them with the same ILIKE it uses for every other field.

TRAIT_INDEX_SOURCE_KEY = "image_meta_traits"

# Bumped whenever the shape of the index changes. A fingerprint describes the
# inputs, not the output, as with PROVENANCE_SCHEMA_VERSION.
TRAITS_SCHEMA_VERSION = 1

# Wing size is relative: terciles of upper wingspan over the species the
# collection holds, not over all of LepTraits. Against every butterfly family
# nearly every nymphalid would be "large", and the class would filter nothing.
WING_SIZE_CLASSES = ("Small", "Medium", "Large")

MONTH_COLUMNS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)  # fmt: skip

# Every LepTraits column the index reads. A consensus file without one of
# them yields NULL for it rather than failing the build.
_SOURCE_COLUMNS = (
    "Species",
    "WS_U",
    "WS_U_Fem",
    "WS_U_Mal",
    *MONTH_COLUMNS,
    "DiapauseStage",
    "Voltinism",
    "OvipositionStyle",
    "CanopyAffinity",
    "EdgeAffinity",
    "MoistureAffinity",
    "DisturbanceAffinity",
    "NumberOfHostplantFamilies",
    "SoleHostplantFamily",
    "PrimaryHostplantFamily",
    "SecondaryHostplantFamily",
)

# Index column -> expression over the cleaned LepTraits row, decoded to the
# words a reader searches with.
_DECODED_COLUMNS = {
    "canopy_affinity": '"CanopyAffinity"',
    "edge_affinity": '"EdgeAffinity"',
    "moisture_affinity": '"MoistureAffinity"',
    "disturbance_affinity": '"DisturbanceAffinity"',
    "voltinism": """CASE upper("Voltinism")
                WHEN 'U' THEN 'Univoltine'
                WHEN 'B' THEN 'Bivoltine'
                WHEN 'M' THEN 'Multivoltine'
                ELSE "Voltinism" END""",
    "diapause_stage": """nullif(concat_ws(', ',
                CASE WHEN contains(upper("DiapauseStage"), 'E') THEN 'Egg' END,
                CASE WHEN contains(upper("DiapauseStage"), 'L') THEN 'Larva' END,
                CASE WHEN contains(upper("DiapauseStage"), 'P') THEN 'Pupa' END,
                CASE WHEN contains(upper("DiapauseStage"), 'A') THEN 'Adult' END
            ), '')""",
    "oviposition_style": """nullif(concat_ws(', ',
                CASE WHEN contains(upper("OvipositionStyle"), 'S') THEN 'Single' END,
                CASE WHEN contains(upper("OvipositionStyle"), 'C') THEN 'Clustered' END
            ), '')""",
    "hostplant_families": """nullif(array_to_string(list_sort(list_distinct(
                list_filter(
                    ["SoleHostplantFamily", "PrimaryHostplantFamily",
                     "SecondaryHostplantFamily"],
                    family -> family IS NOT NULL
                ))), ', '), '')""",
    "host_breadth": """CASE
                WHEN try_cast("NumberOfHostplantFamilies" AS INTEGER) = 1
                    THEN 'Specialist'
                WHEN try_cast("NumberOfHostplantFamilies" AS INTEGER) = 2
                    THEN 'Oligophagous'
                WHEN try_cast("NumberOfHostplantFamilies" AS INTEGER) >= 3
                    THEN 'Generalist'
            END""",
    "flight_months": "nullif(concat_ws(', ', "
    + ", ".join(
        f"CASE WHEN \"{month}\" = '1' THEN '{month}' END" for month in MONTH_COLUMNS
    )
    + "), '')",
    "wingspan_cm": """coalesce(
                try_cast("WS_U" AS DOUBLE),
                try_cast("WS_U_Fem" AS DOUBLE),
                try_cast("WS_U_Mal" AS DOUBLE))""",
}

TRAIT_INDEX_COLUMNS = (*_DECODED_COLUMNS, "wing_size")


def _normalized_name(expression: str) -> str:
    """Lower-case, single-spaced, underscores as spaces: the CoL `name_norm`."""
    return (
        f"lower(regexp_replace(trim(replace({expression}, '_', ' ')), "
        "'\\s+', ' ', 'g'))"
    )


def _binomial(expression: str) -> str:
    """The first two words of a normalized name, or NULL for a single word."""
    words = f"string_split({_normalized_name(expression)}, ' ')"
    return (
        f"CASE WHEN len({words}) >= 2 "
        f"THEN array_to_string(list_slice({words}, 1, 2), ' ') END"
    )


class TraitIndexService:
    """Build `image_meta_traits`: LepTraits keyed to each occurrence image."""

    def __init__(self, duckdb: DuckDBClient):
        config = LepTraitConfig()
        self.source_table = config.table
        self.table = config.index_table
        self.image_meta_table = ImageMetaConfig().table
        col = ColConfig()
        self.backbone_table = col.table
        self.status_table = col.occurrence_status_table
        self.db_client = duckdb

    def ensure(self) -> bool:
        """Rebuild if the index is missing or out of date.

        Returns True when it was rebuilt. Never raises: without the index the
        trait searches report themselves unavailable and nothing else changes.
        """
        for table in (self.source_table, self.image_meta_table):
            if not self.db_client.table_exists(table):
                logger.warning(f"No '{table}' table; skipping the trait index.")
                return False

        fingerprint = self._source_fingerprint()
        state = IngestionState(self.db_client)
        if state.is_current(TRAIT_INDEX_SOURCE_KEY, fingerprint) and (
            self.db_client.table_exists(self.table)
        ):
            logger.info("Trait index is already current; skipping.")
            return False

        try:
            self._build()
        except (duckdb.Error, ValueError) as error:
            logger.error(f"Trait index build failed: {error}")
            return False

        state.mark(TRAIT_INDEX_SOURCE_KEY, fingerprint)
        logger.info(f"Trait index built; {self.count_entries():,} occurrences.")
        return True

    def _source_fingerprint(self) -> str:
        """Row counts of every input, plus whether each optional one exists.

        The backbone and the taxonomy run arriving later changes how names
        resolve, so their presence is part of the token, not just their size.
        """
        parts = []
        for table in (
            self.source_table,
            self.image_meta_table,
            self.status_table,
            self.backbone_table,
        ):
            if self.db_client.table_exists(table):
                count_row = self.db_client.execute(
                    f"SELECT count(*) FROM {table}"
                ).fetchone()
                count = count_row[0] if count_row is not None else 0
                parts.append(str(count))
            else:
                parts.append("-")
        return ":".join(parts) + f":v{TRAITS_SCHEMA_VERSION}"

    def count_entries(self) -> int:
        row = self.db_client.execute(f"SELECT count(*) FROM {self.table}").fetchone()
        return row[0] if row is not None else 0

    def _cleaned_source(self) -> str:
        """LepTraits as text, with the file's 'NA' and blanks read as NULL."""
        projection = []
        for column in _SOURCE_COLUMNS:
            if self.db_client.column_exists(self.source_table, column):
                value = f"nullif(nullif(trim(CAST(\"{column}\" AS VARCHAR)), 'NA'), '')"
            else:
                value = "CAST(NULL AS VARCHAR)"
            projection.append(f'{value} AS "{column}"')
        return f"SELECT {', '.join(projection)} FROM {self.source_table}"

    def _resolution(self) -> str:
        """CTEs mapping each LepTraits name to the accepted CoL binomial.

        The same order `ColTaxonSearch.search` tries: the name as written,
        then its canonical form, preferring an accepted usage. A synonym
        follows its `accepted_id`; a subspecies folds into its species. A name
        CoL does not know keeps its own spelling.
        """
        if not self.db_client.table_exists(self.backbone_table):
            logger.info(
                "No CoL backbone; LepTraits names join the collection as written."
            )
            return """
    resolved AS (
        SELECT trait_name, CAST(NULL AS VARCHAR) AS accepted_binomial
        FROM names
    )"""
        col = self.backbone_table
        return f"""
    by_name AS (
        SELECT n.trait_name, c.accepted_id
        FROM names n JOIN {col} c ON c.name_norm = n.trait_name
        QUALIFY row_number() OVER (
            PARTITION BY n.trait_name ORDER BY c.is_accepted DESC, c.usage_id
        ) = 1
    ), by_canonical AS (
        SELECT n.trait_name, c.accepted_id
        FROM names n JOIN {col} c ON c.canonical_key = n.trait_name
        WHERE n.trait_name NOT IN (SELECT trait_name FROM by_name)
        QUALIFY row_number() OVER (
            PARTITION BY n.trait_name ORDER BY c.is_accepted DESC, c.usage_id
        ) = 1
    ), resolved AS (
        SELECT hit.trait_name,
               CASE WHEN accepted.genus_norm IS NOT NULL
                         AND accepted.epithet_norm IS NOT NULL
                    THEN accepted.genus_norm || ' ' || accepted.epithet_norm
               END AS accepted_binomial
        FROM (SELECT * FROM by_name UNION ALL SELECT * FROM by_canonical) hit
        LEFT JOIN {col} accepted ON accepted.usage_id = hit.accepted_id
    )"""

    def _occurrence_species(self) -> str:
        """FROM/WHERE giving each occurrence's species, normalized.

        The accepted species of a MATCHED record when a harmonization run is
        loaded, so the index covers exactly the images that have a species
        page. Before any run, the recorded binomial is all there is.
        """
        if self.db_client.table_exists(self.status_table):
            return f"""
        SELECT o.img_id, lower(t.accepted_species_name) AS species_norm
        FROM {self.image_meta_table} o
        JOIN {self.status_table} t USING (img_id)
        WHERE t.update_status = 'MATCHED'
          AND t.accepted_species_name IS NOT NULL"""
        return f"""
        SELECT img_id, {_binomial("species")} AS species_norm
        FROM {self.image_meta_table}"""

    def _build(self) -> None:
        decoded = ",\n            ".join(
            f"{expression} AS {name}" for name, expression in _DECODED_COLUMNS.items()
        )
        # Several LepTraits rows can land on one species: exact duplicates in
        # the file, and synonyms CoL folds together. One row per species keeps
        # the join to occurrences one-to-one; each trait takes its first
        # recorded value, from the row named as the accepted species if any.
        collapsed = ",\n            ".join(
            f"first({name} ORDER BY {name} IS NULL, "
            f"trait_name = species_norm DESC, trait_name) AS {name}"
            for name in _DECODED_COLUMNS
        )
        columns = ", ".join(f"s.{name}" for name in _DECODED_COLUMNS)
        sizes = "[" + ", ".join(f"'{size}'" for size in WING_SIZE_CLASSES) + "]"
        self.db_client.execute(
            f"""
    CREATE OR REPLACE TABLE {self.table} AS
    WITH cleaned AS ({self._cleaned_source()}
    ), decoded AS (
        SELECT {_normalized_name('"Species"')} AS trait_name,
            {decoded}
        FROM cleaned
        WHERE "Species" IS NOT NULL
    ), names AS (
        SELECT DISTINCT trait_name FROM decoded
    ), {self._resolution()}
    , named AS (
        SELECT d.*, coalesce(r.accepted_binomial, d.trait_name) AS species_norm
        FROM decoded d LEFT JOIN resolved r USING (trait_name)
    ), species AS (
        SELECT species_norm,
            first(trait_name ORDER BY trait_name = species_norm DESC, trait_name)
                AS leptraits_name,
            {collapsed}
        FROM named
        GROUP BY species_norm
    ), occurrences AS ({self._occurrence_species()}
    ), sized AS (
        SELECT species_norm,
               list_extract({sizes}, ntile(3) OVER (ORDER BY wingspan_cm))
                   AS wing_size
        FROM species
        WHERE wingspan_cm IS NOT NULL
          AND species_norm IN (SELECT species_norm FROM occurrences)
    )
    SELECT o.img_id,
           s.species_norm AS trait_species,
           s.leptraits_name,
           {columns},
           sized.wing_size
    FROM occurrences o
    JOIN species s USING (species_norm)
    LEFT JOIN sized USING (species_norm)
            """
        )
        self.db_client.execute(
            f"CREATE INDEX IF NOT EXISTS {self.table}_img_idx ON {self.table} (img_id)"
        )
