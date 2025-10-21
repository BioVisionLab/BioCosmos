from pydantic import BaseModel
from fastapi import Request
from ..services.images import ImagePersistData
from ..services.leptraits import LepTraits
from ..services.gbif import GbifTaxonSearch, GbifPersistData
from ..services.openai import AiSummary
import logging

logger = logging.getLogger(__name__)

# class TaxonStatPayload(BaseModel):
#    """
#    A class to represent taxon statistics from GBIF and LepTraits entries.
#    """
#    gbifEntries: int
#    lepTraitsEntries: int
#    imageEntries: int
#    gbifSpeciesCount: int
#    return cls(
#        gbifEntries =
#    )


class TaxonStatPayload(BaseModel):
    """
    A class to represent taxon statistics from GBIF and LepTraits entries.
    """

    gbifEntries: int
    lepTraitsEntries: int
    imageEntries: int
    gbifSpeciesCount: int

    @classmethod
    def from_data(
        cls,
        gbif_entries: int | None,
        lep_traits_entries: int | None,
        image_entries: int | None,
        gbif_species_count: int | None,
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
            gbifEntries=gbif_entries
            if gbif_entries is not None
            else 0,
            lepTraitsEntries=lep_traits_entries
            if lep_traits_entries is not None
            else 0,
            imageEntries=image_entries
            if image_entries is not None
            else 0,
            gbifSpeciesCount=gbif_species_count
            if gbif_species_count is not None
            else 0,
        )


class SpeciesPayload(BaseModel):
    """
    A class to represent a species payload for search operations.
    It includes the species taxonomy and traits data.
    """

    speciesId: str
    taxonomy: dict
    traits: dict
    similarSpecies: list[dict] = []

    @classmethod
    def from_data(
        cls,
        species_id: str,
        taxonomy: dict,
        traits: dict,
        similarSpecies: list[dict],
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
            similarSpecies=similarSpecies,
        )


class TaxonSearch:
    """
    A class to handle taxon search operations using the GBIF API.
    """

    def __init__(self, request: Request, query: str = ""):
        """
        Initialize the TaxonSearch class.
        Args:
            query (str): The species name to search for.
        """
        self.species = query.strip().lower()
        if "_" in self.species:
            self.species = self.species.replace("_", " ").strip()
        self.request = request

    def get_counts(self) -> dict | None:
        """
        Get the counts of species in each taxon.
        """
        gbif_service = GbifPersistData(
            duckdb=self.request.app.state.duck_db
        )
        leptraits_service = LepTraits(
            duckdb=self.request.app.state.duck_db
        )
        img_service = ImagePersistData(
            lance_db=self.request.app.state.lance_db
        )
        try:
            counts_gbif: int | None = gbif_service.count_entries()
            count_leptrait: int | None = (
                leptraits_service.count_entries()
            )
            count_img: int | None = img_service.entries()
            count_unique_species: int | None = (
                gbif_service.count_unique_species()
            )

            if (
                counts_gbif is None
                and count_leptrait is None
                and count_img is None
                and count_unique_species is None
            ):
                logger.info("No counts data found.")
                return None
            logger.info(
                f"Counts data found: {counts_gbif}, {count_leptrait}"
            )

            payload = TaxonStatPayload.from_data(
                gbif_entries=counts_gbif,
                lep_traits_entries=count_leptrait,
                image_entries=count_img,
                gbif_species_count=count_unique_species,
            )
            return payload.model_dump()
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

        try:
            taxon_data = await self._get_gbif_data()
            trait_data = self._get_traits()
            if trait_data is None:
                logger.info(
                    f"No traits data found for species: {self.species}"
                )
                return None
            similar_images: list[dict] = (
                ImagePersistData(
                    lance_db=self.request.app.state.lance_db
                ).fetch_id_similar_images(
                    species_name=self.species, limit=50
                )
                or []
            )
            payload = SpeciesPayload.from_data(
                species_id=self.species,
                taxonomy=taxon_data,
                traits=trait_data,
                similarSpecies=similar_images,
            )
            return payload.model_dump()

        except Exception as e:
            logger.error(
                f"Error searching for taxon: {e}", exc_info=True
            )
            return None
        finally:
            logger.info("Closed GBIF client connection")

    async def generate_summary(self) -> str | None:
        """
        Generate a summary for the species using an AI service.

        Returns:
            str | None: The generated summary or None if not found.
        """
        if not self.species:
            return None
        try:
            taxon_data = await self._get_gbif_data()
            traits = self._get_traits()
            prompt = self._generate_prompt(taxon_data, traits)
            if prompt is None or prompt.strip() == "":
                logger.info(
                    f"No valid prompt could be generated for species: {self.species}"
                )
                return None
            summarizer = AiSummary()
            summary = summarizer.summarize_text(prompt)

            if summary is None:
                message = f"No summary could be generated for species: {self.species}"
                logger.info(message)
                return None

            logger.info(
                f"Summary generated for species: {self.species}"
            )
            return summary

        except Exception as e:
            logger.error(
                f"Error generating summary for species {self.species}: {e}",
                exc_info=True,
            )
            return None

    def _generate_prompt(self, taxon_data: dict, traits: dict) -> str:
        """
        Generate a prompt for the AI summarization service based on taxon data and traits.

        Args:
            taxon_data (dict): The taxonomy data for the species.
            traits (dict): The traits data for the species.

        Returns:
            str: The generated prompt.
        """
        prompt = ""
        if taxon_data:
            prompt += "Taxonomy Information:\n"
            for key, value in taxon_data.items():
                prompt += f"- {key.capitalize()}: {value}\n"
            prompt += "\n"
        if traits:
            prompt += "Traits Information:\n"
            for key, value in traits.items():
                prompt += f"- {key.capitalize()}: {value}\n"
            prompt += "\n"
        prompt += "Please provide a brief overview of the species based on the above information."
        return prompt

    async def _get_gbif_data(self) -> dict:
        """
        Fetch GBIF data for the species using the GbifPersistData service.

        Returns:
            dict: A dictionary containing the species GBIF data or None if not found.
        """
        gbif_service = GbifTaxonSearch()
        try:
            gbif_data = await gbif_service.search(self.species)
            if gbif_data is None:
                logger.info(
                    f"No GBIF data found for species: {self.species}"
                )
                return {}
            logger.info(
                f"Found GBIF data for species: {self.species}. Data: {gbif_data}"
            )
            return gbif_data
        except Exception as e:
            logger.error(
                f"Error fetching GBIF data for species {self.species}: {e}",
                exc_info=True,
            )
            return {}
        finally:
            await gbif_service.close()

    def _get_traits(self) -> dict | None:
        """
        Fetch traits for the species using the LepTraits service.

        Returns:
            dict: A dictionary containing the species traits data or None if not found.
        """
        try:
            leptraits = LepTraits(
                duckdb=self.request.app.state.duck_db
            )
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
