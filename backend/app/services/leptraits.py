import logging
from venv import logger

from ..database.duckdb import DuckDBClient
from ..database.model import LepTraitData

logger = logging.getLogger(__name__)


LEP_TRAITS_DOWNLOAD = "https://raw.githubusercontent.com/hhandika/LepTraits/refs/heads/main/consensus/consensus.csv"


class LepTraits:
    def __init__(self):
        """
        Initializes the LepTraits service.
        This service connects to the DuckDB database to fetch traits for lepidopteran species.
        The caller is responsible for managing the database connection lifecycle.
        """
        self.db_client = DuckDBClient()

    def ingest(self, csv_path: str = LEP_TRAITS_DOWNLOAD):
        """
        Ingests the LepTraits consensus CSV data into the DuckDB database.
        :param csv_path: The path to the LepTraits consensus CSV file.
        """
        try:
            self.db_client.create_if_not_exists_csv(
                table_name="lep_traits_consensus", csv_path=csv_path
            )
            logger.info(
                f"LepTraits data ingested successfully from '{csv_path}'."
            )
        except Exception as e:
            logger.error(
                f"Failed to ingest LepTraits data from '{csv_path}': {e}"
            )
            raise e

    def get(self, species_name: str) -> dict:
        """
        Fetches traits for a given species from the lep_traits_consensus table.
        :param species_name: The name of the species to fetch traits for.
        :return: The traits data for the species.
        """
        query = "SELECT * FROM lep_traits_consensus WHERE LOWER(Species) = LOWER(?)"
        result = self.db_client.execute(query, [species_name]).pl()
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

    def close(self):
        """
        Closes the database client connection.
        """
        if self.db_client:
            self.db_client.close()
            logger.info(
                "LepTraits database client connection closed."
            )
        else:
            logger.warning(
                "LepTraits database client was not initialized."
            )
