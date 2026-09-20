import logging

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from ..configs.config import GbifConfig
from ..database.duckdb import DuckDBClient, FtsSearchData


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GBIF_COLUMNS_INDEXED = [
    "species",
    "genus",
    "family",
    "order",
    "vernacularName",
    "sex",
    "lifeStage",
    "continent",
    "island",
    "countryCode",
    "stateProvince",
    "county",
    "municipality",
    "locality",
    "verbatimLocality",
    "level1Name",
]


GBIF_INDEX_ID = "rowid"


class SearchGbifData(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    species: str
    matched_fields: list[str] = []
    score: float = 0.0

    @field_serializer("score")
    def serialize_score(self, score: float) -> float:
        return round(score, 4)


class GbifPersistData:
    """
    GBIF persistence data model.
    Allowing to ingest, store, and query GBIF species data.
    """

    def __init__(self, duckdb: DuckDBClient):
        """
        Initialize the GbifPersistData from DuckDB.
        """
        config = GbifConfig()
        self.tsv_path = config.path
        self.table_name = config.table
        self.skip_ingestion = config.skip
        self.db_client = duckdb

    def ingest(self):
        """
        Ingest GBIF data from a TSV file into DuckDB.
        """
        if self.skip_ingestion:
            logger.info("Skipping GBIF data ingestion as per configuration.")
            return
        try:
            # We use custom execution instead of the wrapper function
            # for table creation in the DuckDb module to avoid
            # issues with type inference.
            self.db_client.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name} AS SELECT * FROM read_csv_auto('{self.tsv_path}', delim='\t', types={{'georeferencedDate': 'VARCHAR'}})"
            )
            logger.info(f"GBIF data ingested successfully from '{self.tsv_path}'.")
            entries: int | None = self.count_entries()
            self._index_columns()
            logger.info("Full-text search index created on GBIF metadata table.")
            logger.info(f"Total entries after ingestion: {entries}")
        except Exception as e:
            logger.error(f"Failed to ingest GBIF data from '{self.tsv_path}': {e}")
            raise e

    def count_entries(self) -> int | None:
        """
        Count the number of entries in the GBIF metadata table.
        """
        try:
            query = f"SELECT COUNT(*) AS total_rows FROM {self.table_name}"
            result = self.db_client.execute(query).fetchall()
            logger.info(f"Counted {result[0][0]} entries in GBIF metadata table.")
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Failed to count entries in GBIF metadata table: {e}")
            return None

    def count_unique_species(self) -> int | None:
        try:
            query = f"SELECT COUNT(DISTINCT species) FROM {self.table_name}"
            result = self.db_client.execute(query).fetchone()[0]
            logger.info(f"Counted {result} unique species in GBIF metadata table.")
            return result if result else None
        except Exception as e:
            logger.error(f"Failed to count unique species in GBIF metadata table: {e}")
            return None

    def get(self, species_name: str) -> dict | None:
        """
        Fetch GBIF data for a given species name.
        :param species_name: The name of the species to fetch data for.
        :return: The GBIF data for the species or None if not found.
        """
        query = "SELECT * FROM gbif_meta WHERE LOWER(species) = LOWER(?)"
        result = self.db_client.execute(query, [species_name]).pl()
        if result.is_empty():
            logger.warning(f"No GBIF data found for species '{species_name}'.")
            return None
        if len(result) > 1:
            logger.warning(
                f"Multiple entries found for species '{species_name}'. Returning the first entry."
            )
        gbif_data = result.to_dicts()[0]
        return gbif_data

    def search_any(self, query: str, limit: int = 100) -> list[SearchGbifData]:
        """
        Search for species by any column matching the query string.
        Uses FTS indexing for efficient searching across multiple columns.
        Returns unique species ordered by best BM25 score.
        """
        try:
            query = (query or "").strip()
            if not query:
                logger.warning("Empty query passed to search_any")
                return []

            results: list[FtsSearchData] = self.db_client.search_fts(
                table_name=self.table_name,
                id_column=GBIF_INDEX_ID,
                query=query,
                fields=GBIF_COLUMNS_INDEXED,
                limit=limit,
                unique_species=True,
            )

            if not results:
                logger.warning(f"No species found matching query: {query}")
                return []

            species_list = [
                SearchGbifData(
                    species=r.species, score=r.score, matched_fields=r.matched_fields
                )
                for r in results
            ]

            logger.info(f"Found {len(species_list)} species matching query: {query}")
            return species_list

        except Exception as e:
            logger.error(
                f"Error searching for species with query '{query}': {e}", exc_info=True
            )
            return []

    def search_by_location(self, location: str, limit: int = 500, species_in: list[str] | None = None) -> list[str]:
        """
        Search for species by geographic location.

        Based on the GBIF TSV structure:
        - level0Name: Country name (e.g., "Colombia", "Ecuador")
        - countryCode: ISO country code (e.g., "CO", "EC")
        - stateProvince: State/province name
        - level1Name: First-level administrative division
        - continent: Continent (usually uppercase like "SOUTH_AMERICA")
        - locality: Specific locality
        - verbatimLocality: Verbatim locality from source
        """
        try:
            location = (location or "").strip()
            if not location:
                logger.warning("Empty location passed to search_by_location")
                return []

            location_upper = location.upper()

            # Escape single quotes for SQL
            loc_esc = location.replace("'", "''")
            loc_upper_esc = location_upper.replace("'", "''")

            if len(location) <= 3:
                # For ISO country codes or state acronyms (e.g. 'BR', 'ID', 'TX', 'USA'), perform exact match
                # otherwise a fuzzy LIKE '%BR%' would brutally false-match any verbatimLocality string containing "br"
                conditions = [
                    f"countryCode = '{location_upper}'",
                    f"UPPER(level0Name) = '{location_upper}'",
                    f"UPPER(stateProvince) = '{location_upper}'",
                ]
            else:
                # Broad fuzzy matching for full names and regions
                conditions = [
                    f"LOWER(level0Name)      LIKE LOWER('%{loc_esc}%')",
                    f"LOWER(countryCode)     LIKE LOWER('%{loc_esc}%')",
                    f"LOWER(stateProvince)   LIKE LOWER('%{loc_esc}%')",
                    f"LOWER(level1Name)      LIKE LOWER('%{loc_esc}%')",
                    f"LOWER(locality)        LIKE LOWER('%{loc_esc}%')",
                    f"LOWER(verbatimLocality)LIKE LOWER('%{loc_esc}%')",
                    (
                        f"(continent LIKE '%{loc_upper_esc}%' "
                        f" OR LOWER(continent) LIKE LOWER('%{loc_esc}%'))"
                    ),
                ]

            where_clause = " OR ".join(conditions)
            
            if species_in:
                safe_species = [s.replace("'", "''").lower().replace(" ", "_") for s in species_in]
                species_list = ", ".join(f"'{s}'" for s in safe_species)
                where_clause = f"({where_clause}) AND LOWER(REPLACE(species, ' ', '_')) IN ({species_list})"

            query = f"""
                SELECT DISTINCT species
                FROM {self.table_name}
                WHERE {where_clause}
                LIMIT {int(limit)}
            """

            logger.info(f"Searching for location '{location}' in GBIF table")
            result = self.db_client.execute(query).pl()

            if result.is_empty():
                logger.warning(f"No species found in location: {location}")
                return []

            species_list = [
                s for s in result["species"].to_list() if s and str(s).strip()
            ]

            logger.info(f"Found {len(species_list)} species in location: {location}")
            return species_list

        except Exception as e:
            logger.error(
                f"Error searching by location '{location}': {e}",
                exc_info=True,
            )
            return []

    def search_by_country_code(
        self,
        country_code: str,
        limit: int = 500,
    ) -> list[str]:
        """Return distinct species for an ISO 3166-1 alpha-2 country code."""
        normalized_code = (country_code or "").strip().upper()
        if len(normalized_code) != 2 or not normalized_code.isalpha():
            raise ValueError("A two-letter country code is required.")

        query = f"""
            SELECT DISTINCT species
            FROM {self.table_name}
            WHERE UPPER(countryCode) = ?
            ORDER BY species
            LIMIT ?
        """
        result = self.db_client.execute_prepared_to_pl(
            query,
            [normalized_code, int(limit)],
        )
        if result.is_empty():
            return []
        return [
            str(species).strip()
            for species in result["species"].to_list()
            if species and str(species).strip()
        ]


    def _index_columns(self):
        """
        Create a full-text search index on relevant columns for location-based searches.
        This can significantly improve performance for search queries that filter by location.
        """
        try:
            self.db_client.index_table(
                table_name=self.table_name,
                id_column=GBIF_INDEX_ID,
                columns=GBIF_COLUMNS_INDEXED,
                overwrite=True,  # safe to re-run on restart
            )
        except Exception as e:
            logger.error(f"Failed to create full-text search index on GBIF table: {e}")
            raise
