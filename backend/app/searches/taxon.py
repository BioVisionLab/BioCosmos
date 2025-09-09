from pydantic import BaseModel

from ..services.images import ImagePersistData
from ..services.leptraits import LepTraits
from ..services.gbif import GbifTaxonSearch, GbifPersistData
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
    similar_images: list[str] = []

    @classmethod
    def from_data(
        cls,
        species_id: str,
        taxonomy: dict,
        traits: dict,
        similar_images: list[str],
    ):
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
            traits=traits,
            similar_images=similar_images,
        )


class TaxonSearch:
    """
    A class to handle taxon search operations using the GBIF API.
    """

    def __init__(self, query: str = ""):
        """
        Initialize the TaxonSearch class.
        Args:
            query (str): The species name to search for.
        """
        self.species = query.strip().lower()

    def get_counts(self) -> dict | None:
        """
        Get the counts of species in each taxon.
        """
        gbif_service = GbifPersistData()
        leptraits_service = LepTraits()
        img_service = ImagePersistData()
        try:
            counts_gbif: int | None = gbif_service.count_entries()
            count_leptrait: int | None = (
                leptraits_service.count_entries()
            )
            count_img: int | None = img_service.entries()

            if (
                counts_gbif is None
                and count_leptrait is None
                and count_img is None
            ):
                logger.info("No counts data found.")
                return None
            logger.info(
                f"Counts data found: {counts_gbif}, {count_leptrait}"
            )
            return {
                "GBIF entries": counts_gbif,
                "LepTraits entries": count_leptrait,
                "Image entries": count_img,
            }
        except Exception as e:
            logger.error(f"Error fetching counts: {e}", exc_info=True)
            return None

    async def search(self) -> dict | None:
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
            if trait_data is None:
                logger.info(
                    f"No traits data found for species: {self.species}"
                )
                return None
            similar_images = (
                ImagePersistData().fetch_id_similar_images(
                    species_name=self.species, limit=20
                )
                or []
            )
            payload = SpeciesPayload.from_data(
                species_id=self.species,
                taxonomy=taxon_data,
                traits=trait_data,
                similar_images=similar_images,
            )
            return payload.model_dump()

        except Exception as e:
            logger.error(
                f"Error searching for taxon: {e}", exc_info=True
            )
            return None
        finally:
            await gbif_service.close()
            logger.info("Closed GBIF client connection")

    def get_traits(self) -> dict | None:
        """
        Fetch traits for the species using the LepTraits service.

        Returns:
            dict: A dictionary containing the species traits data or None if not found.
        """
        try:
            leptraits = LepTraits()
            leptraits_data = leptraits.get(self.species)
            if leptraits_data is None:
                logger.info(
                    f"No traits data found for species: {self.species}"
                )
                return None
            logger.info(
                f"Found traits data for species: {self.species}. Data: {leptraits_data}"
            )
            return leptraits_data
        except Exception as e:
            logger.error(
                f"Error fetching traits for species {self.species}: {e}",
                exc_info=True,
            )
            return None
        finally:
            leptraits.close()
            logger.info("LepTraits client connection closed")
