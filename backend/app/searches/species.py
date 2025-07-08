from ..services.gbif import GbifTaxonSearch
import logging

logger = logging.getLogger(__name__)


class TaxonSearch:
    """
    A class to handle taxon search operations using the GBIF API.
    """

    def __init__(self, query: str = ""):
        """
        Initialize the TaxonSearch class with an optional query.
        Args:
            query (str): The species name to search for. Defaults to an empty string.
        """
        self.query = query.strip().lower() if query else ""

    async def search(self):
        """
        Search for species taxonomy data using the GBIF API.

        Args:
            query (str): The species name to search for.

        Returns:
            dict: A dictionary containing the species taxonomy data or None if not found.
        """
        if not self.query:
            return None

        if "_" in self.query:
            self.query = self.query.replace("_", " ")

        gbif_service = GbifTaxonSearch()
        try:
            taxon_data = await gbif_service.search(self.query)
            if taxon_data is None:
                logger.info(
                    f"No data found for species: {self.query}"
                )
                return None
            logger.info(f"Taxon data found for: {self.query}")
            return taxon_data
        except Exception as e:
            logger.error(
                f"Error searching for taxon: {e}", exc_info=True
            )
            return None
        finally:
            await gbif_service.close()
            logger.info("Closed GBIF client connection")
