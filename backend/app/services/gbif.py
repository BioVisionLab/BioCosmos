from ..configs.config import GbifConfig
from ..database.duckdb import DuckDBClient
from ..database.model import SpeciesTaxonomy
import logging
import httpx

GBIF_HOST = "https://api.gbif.org/v1/species"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        self.db_client = duckdb

    def ingest(self):
        """
        Ingest GBIF data from a TSV file into DuckDB.
        """
        try:
            # We use custom execution instead of the wrapper function
            # for table creation in the DuckDb module to avoid
            # issues with type inference.
            self.db_client.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name} AS SELECT * FROM read_csv_auto('{self.tsv_path}', delim='\t', types={{'georeferencedDate': 'VARCHAR'}})"
            )
            logger.info(
                f"GBIF data ingested successfully from '{self.tsv_path}'."
            )
            entries: int | None = self.count_entries()
            logger.info(f"Total entries after ingestion: {entries}")
        except Exception as e:
            logger.error(
                f"Failed to ingest GBIF data from '{self.tsv_path}': {e}"
            )
            raise e

    def count_entries(self) -> int | None:
        """
        Count the number of entries in the GBIF metadata table.
        """
        try:
            query = f"SELECT COUNT(*) AS total_rows FROM {self.table_name}"
            result = self.db_client.execute(query).fetchall()
            logger.info(
                f"Counted {result[0][0]} entries in GBIF metadata table."
            )
            return result[0][0] if result else None
        except Exception as e:
            logger.error(
                f"Failed to count entries in GBIF metadata table: {e}"
            )
            return None

    def get(self, species_name: str) -> dict | None:
        """
        Fetch GBIF data for a given species name.
        :param species_name: The name of the species to fetch data for.
        :return: The GBIF data for the species or None if not found.
        """
        query = (
            "SELECT * FROM gbif_meta WHERE LOWER(species) = LOWER(?)"
        )
        result = self.db_client.execute(query, [species_name]).pl()
        if result.is_empty():
            logger.warning(
                f"No GBIF data found for species '{species_name}'."
            )
            return None
        if len(result) > 1:
            logger.warning(
                f"Multiple entries found for species '{species_name}'. Returning the first entry."
            )
        gbif_data = result.to_dicts()[0]
        return gbif_data


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
            raise Exception(
                f"Error fetching data from GBIF: {response.text}"
            )

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
            logger.info(
                f"No Red List status found for GBIF key: {gbif_key}"
            )
            logger.info(
                "Setting Red List category to 'Unknown' for this taxon."
            )
            redlist_category = "Unknown"
        logger.info(
            f"Red List category for GBIF key {gbif_key}: {redlist_category}"
        )
        taxon = SpeciesTaxonomy.from_json(
            first_result, redlist_category
        )
        taxon_dump = self._revert_clean_results(
            taxon.model_dump(by_alias=True)
        )
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

    async def _get_redlist_status(
        self, gbif_key: int | None
    ) -> str | None:
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
            logger.info(
                f"No Red List status found for GBIF key: {gbif_key}"
            )
            return None
        logger.info(
            f"Red List status for GBIF key {gbif_key}: {data.get('code')}"
        )
        return data.get("code", None)

    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
        logger.info("Closed GBIF client connection.")


if __name__ == "__main__":
    import asyncio

    async def main():
        gbif_service = GbifTaxonSearch()
        try:
            result = await gbif_service.search("Danaus plexippus")
            if result:
                print(result)
            else:
                print("No results found.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await gbif_service.close()

    asyncio.run(main())
