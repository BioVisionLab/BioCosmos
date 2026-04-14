import logging
import httpx

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from ..configs.config import GbifConfig
from ..database.duckdb import DuckDBClient, FtsSearchData
from ..database.model import SpeciesTaxonomy

GBIF_HOST = "https://api.gbif.org/v1/species"


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

    def search_by_location(self, location: str, limit: int = 500) -> list[str]:
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


class GbifTaxonSearch:
    """
    Service for searching GBIF taxon names.
    """

    def __init__(self):
        """
        Initialize the GbifTaxonSearch service.
        """
        self.host = GBIF_HOST
        self.client = httpx.AsyncClient()

    async def search(self, query: str) -> dict | None:
        """
        Search for taxon names in GBIF.

        Check if the result is empty, and if so, return None.
        """
        url = f"{self.host}?name={query}&offset=0&limit=1"
        logger.info(f"Searching GBIF for query: {query}")
        logger.info(f"Constructed URL: {url}")
        response = await self.client.get(url)

        if response.status_code != 200:
            raise Exception(f"Error fetching data from GBIF: {response.text}")

        data = response.json()
        if not data.get("results"):
            logger.info(f"No results found for query: {query}")
            return None

        # Extract the first result
        first_result: dict = self._clean_results(data["results"][0])
        logger.info(f"Found result: {first_result}")
        gbif_key = first_result.get("key")
        redlist_category = await self._get_redlist_status(gbif_key)
        if redlist_category is None:
            logger.info(f"No Red List status found for GBIF key: {gbif_key}")
            logger.info("Setting Red List category to 'Unknown' for this taxon.")
            redlist_category = "Unknown"
        logger.info(f"Red List category for GBIF key {gbif_key}: {redlist_category}")
        taxon = SpeciesTaxonomy.from_json(first_result, redlist_category)
        taxon_dump = self._revert_clean_results(taxon.model_dump(by_alias=True))
        logger.info(f"Created SpeciesTaxonomy: {taxon}")
        return taxon_dump

    def _clean_results(self, data: dict) -> dict:
        """
        Clean the keys in the dictionary to avoid conflicts with Python reserved keywords.
        This method also avoids pydantic issue with reserved keywords like 'class'.
        """
        if "class" in data:
            data["taxonClass"] = data.pop("class")
        return data

    def _revert_clean_results(self, data: dict) -> dict:
        """
        Revert the cleaning done in _clean_results.
        We need to restore the original key names for consistency with the frontend
        and other platforms that expect the original GBIF data structure.
        """
        if "taxonClass" in data:
            data["class"] = data.pop("taxonClass")
        return data

    async def _get_redlist_status(self, gbif_key: int | None) -> str | None:
        """
        Get the Red List status for a given GBIF key.
        """
        if not gbif_key:
            return None

        url = f"{self.host}/{gbif_key}/iucnRedListCategory"
        response = await self.client.get(url)

        if response.status_code != 200:
            logger.error(
                f"Failed to fetch Red List status for GBIF key {gbif_key}: {response.text}"
            )
            raise Exception(
                f"Error fetching Red List status from GBIF: {response.text}"
            )

        data = response.json()
        if not data:
            logger.info(f"No Red List status found for GBIF key: {gbif_key}")
            return None
        logger.info(f"Red List status for GBIF key {gbif_key}: {data.get('code')}")
        return data.get("code", None)

    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
        logger.info("Closed GBIF client connection.")
