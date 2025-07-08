import logging
from venv import logger

logger = logging.getLogger(__name__)


class LepTraitService:
    def __init__(self, db_client):
        self.db_client = db_client

    def get_traits(self, species_name: str) -> dict:
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
