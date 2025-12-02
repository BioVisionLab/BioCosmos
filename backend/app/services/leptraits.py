import logging
from math import log
from venv import logger
from ..configs.config import LepTraitConfig
from ..database.duckdb import DuckDBClient
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
        self.db_client = duckdb

    def ingest(self):
        """
        Ingests the LepTraits consensus CSV data into the DuckDB database.
        """
        try:
            self.db_client.create_if_not_exists_csv(
                table_name=self.table, csv_path=self.path
            )
            entries: int | None = self.count_entries()
            if entries is not None:
                logger.info(
                    f"LepTraits data ingested successfully from '{self.path}'."
                )
                logger.info(
                    f"Total entries after ingestion: {entries}"
                )
        except Exception as e:
            logger.error(
                f"Failed to ingest LepTraits data from '{self.path}': {e}"
            )
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
            logger.error(
                f"Failed to count entries in lep_traits_consensus table: {e}"
            )
            return None

    def get(self, species_name: str) -> dict:
        """
        Fetches traits for a given species from the lep_traits_consensus table.
        :param species_name: The name of the species to fetch traits for.
        :return: The traits data for the species.
        """
        query = f"SELECT * FROM {self.table} WHERE LOWER(Species) = LOWER('{species_name}')"
        result = self.db_client.execute(query).pl()
        if result.is_empty():
            logger.warning(
                f"No traits found for species '{species_name}'."
            )
            return {}
        if len(result) > 1:
            logger.warning(
                f"Multiple entries found for species '{species_name}'. Returning the first entry."
            )
        traits_data = LepTraitData.from_data(result.to_dicts()[0])
        return traits_data.model_dump()
