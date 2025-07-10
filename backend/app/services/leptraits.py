import logging
from venv import logger

from ..database.duckdb import get_duckdb_client

logger = logging.getLogger(__name__)


class LepTraits:
    def __init__(self, ):
        """
        Initializes the LepTraits service.
        This service connects to the DuckDB database to fetch traits for lepidopteran species.
        The caller is responsible for managing the database connection lifecycle. 
        """
        self.db_client = get_duckdb_client()


    def get(self, species_name: str) -> dict:
        """
        Fetches traits for a given species from the lep_traits_consensus table.
        :param species_name: The name of the species to fetch traits for.
        :return: The traits data for the species.
        """
        query = "SELECT * FROM lep_traits_consensus WHERE species_name = %s"
        result = self.db_client.execute(
            query, (species_name,)
        ).fetchall()
        if not result:
            logger.warning(
                f"No traits found for species '{species_name}'."
            )
            return {}
        if len(result) > 1:
            logger.warning(
                f"Multiple entries found for species '{species_name}'. Returning the first entry."
            )

        return result[0]
    
    def close(self):
        """
        Closes the database client connection.
        """
        if self.db_client:
            self.db_client.close()
            logger.info("LepTraits database client connection closed.")
        else:
            logger.warning("LepTraits database client was not initialized.")
