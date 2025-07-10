from pydantic import BaseModel
from ..services.leptraits import LepTraits
from ..services.gbif import GbifTaxonSearch
import logging

logger = logging.getLogger(__name__)


class SpeciesPayload(BaseModel):
    """
    A class to represent a species payload for search operations.
    It includes the species taxonomy and traits data.
    """
    speciesId: str
    taxonomy: dict
    traits: dict

    @classmethod
    def from_data(cls, species_id: str, taxonomy: dict, traits: dict):
        """
        Create a SpeciesPayload instance from the provided data.
        
        Args:
            species_id (str): The species ID.
            taxonomy (dict): The taxonomy data for the species.
            traits (dict): The traits data for the species.

        Returns:
            SpeciesPayload: An instance of SpeciesPayload.
        """
        return cls(
            speciesId=species_id,
            taxonomy=taxonomy,
            traits=traits
        )
    
class TaxonSearch:
    """
    A class to handle taxon search operations using the GBIF API.
    """

    def __init__(self, query: str):
        """
        Initialize the TaxonSearch class.
        Args:
            query (str): The species name to search for.
        """
        self.species = query.strip().lower()

    async def search(self):
        """
        Search for species taxonomy data using the GBIF API.

        Args:
            query (str): The species name to search for.

        Returns:
            dict: A dictionary containing the species taxonomy data or None if not found.
        """
        if not self.species:
            return None

        if "_" in self.species:
            self.species = self.species.replace("_", " ")
        gbif_service = GbifTaxonSearch()
        try:
            taxon_data = await gbif_service.search(self.species)
            if taxon_data is None:
                logger.info(
                    f"No data found for species: {self.species}"
                )
                return None
            logger.info(f"Taxon data found for: {self.species}")
            trait_data = self.get_traits()
            return SpeciesPayload.from_data(
                id=self.species,
                taxonomy=taxon_data,
                traits=trait_data
            )
        
        except Exception as e:
            logger.error(
                f"Error searching for taxon: {e}", exc_info=True
            )
            return None
        finally:

            await gbif_service.close()
            logger.info("Closed GBIF client connection")

    def get_traits(self):
        """
        Fetch traits for the species using the LepTraits service.

        Returns:
            dict: A dictionary containing the species traits data or None if not found.
        """
        leptraits = LepTraits()
        leptraits_data = leptraits.get(self.species)
        if not leptraits_data:
            logger.info(
                f"No traits data found for species: {self.species}"
            )
            return None
        logger.info(f"Found traits data for species: {self.species}")
        leptraits.close()
        return leptraits_data