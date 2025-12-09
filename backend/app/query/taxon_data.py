from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from fastapi import Request
import polars as pl
import logging

from ..services.image_meta import ImageMetaService
from ..services.images import ImagePersistData
from ..services.leptraits import LepTraits
from ..services.gbif import GbifTaxonSearch, GbifPersistData
from ..services.openai import AiSummary


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
        Create a TaxonStatPayload instance from the provided data.

        Args:
            gbif_entries (int): The number of entries in the GBIF data table.
            lep_traits_entries (int): The number of entries in the Leptraits.
            image_entries (int): The number of image entries
            gbif_species_count (int): The number of unique GBIF species in the occurrence

        Returns:
            TaxonStatPayload: An instance of TaxonStatPayload.
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


class SimilarSpeciesPayload(BaseModel):
    """
    A class to represent similar species data.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    species_name: str
    side: str
    image_id: str
    distance: float


class ClassificationPayload(BaseModel):
    """
    A class to represent taxon classification data.
    """

    matchedCategory: str
    classification: dict

    @classmethod
    def from_data(
        cls,
        matched_category: str,
        classification: dict,
    ):
        """
        Create a ClassificationPayload instance from the provided data.

        Args:
            classification (dict): The classification data for the taxon.
        """
        return cls(
            matchedCategory=matched_category,
            classification=classification,
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
        self.scientific_name = query.strip().lower()
        if "_" in self.scientific_name:
            self.scientific_name = self.scientific_name.replace(
                "_", " "
            ).strip()
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
            lance_db=self.request.app.state.lance_db,
            duckdb=self.request.app.state.duck_db,
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
        if not self.scientific_name:
            return None

        try:
            taxon_data = await self._get_gbif_data()
            trait_data = self._get_traits()
            if trait_data is None:
                logger.info(
                    f"No traits data found for species: {self.scientific_name}"
                )
                return None
            similar_images: list[dict] = SpeciesSimilarity(
                request=self.request
            ).find_similar_species(
                species_name=self.scientific_name, limit=50
            )
            payload = SpeciesPayload.from_data(
                species_id=self.scientific_name,
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

    async def get_classification(self) -> list[dict]:
        """
        Get the taxon classification for the species from the database.

        Returns:
            list[dict]: A list of classification data or None if not found.
        """
        if not self.scientific_name:
            return []

        try:
            gbif_data = await self._get_gbif_data()
            if not gbif_data:
                logger.info(
                    f"No GBIF data found for species: {self.scientific_name}"
                )
                return []
            # We match the query to values and keep track the key where it matched
            matched_data: list[dict] = []
            for key, value in gbif_data.items():
                if (
                    isinstance(value, str)
                    and value.lower() == self.scientific_name.lower()
                ):
                    classification_payload = (
                        ClassificationPayload.from_data(
                            matched_category=key,
                            classification=gbif_data,
                        )
                    )
                    matched_data.append(
                        classification_payload.model_dump()
                    )
            if len(matched_data) > 0:
                logger.info(
                    f"Classification data found for species: {self.scientific_name}"
                )
                return matched_data
            return []

        except Exception as e:
            logger.error(
                f"Error fetching classification for taxon: {e}",
                exc_info=True,
            )
            return []
        finally:
            logger.info("Closed GBIF client connection")

    async def generate_summary(self) -> str | None:
        """
        Generate a summary for the species using an AI service.

        Returns:
            str | None: The generated summary or None if not found.
        """
        if not self.scientific_name:
            return None
        try:
            taxon_data = await self._get_gbif_data()
            traits = self._get_traits()
            prompt = self._generate_prompt(taxon_data, traits)
            if prompt is None or prompt.strip() == "":
                logger.info(
                    f"No valid prompt could be generated for species: {self.scientific_name}"
                )
                return None
            summarizer = AiSummary()
            summary = summarizer.summarize_text(prompt)

            if summary is None:
                message = f"No summary could be generated for species: {self.scientific_name}"
                logger.info(message)
                return None

            logger.info(
                f"Summary generated for species: {self.scientific_name}"
            )
            return summary

        except Exception as e:
            logger.error(
                f"Error generating summary for species {self.scientific_name}: {e}",
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
            gbif_data = await gbif_service.search(
                self.scientific_name
            )
            if gbif_data is None:
                logger.info(
                    f"No GBIF data found for species: {self.scientific_name}"
                )
                return {}
            logger.info(
                f"Found GBIF data for species: {self.scientific_name}. Data: {gbif_data}"
            )
            return gbif_data
        except Exception as e:
            logger.error(
                f"Error fetching GBIF data for species {self.scientific_name}: {e}",
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
            leptraits_data = leptraits.get(self.scientific_name)
            if leptraits_data is None:
                logger.info(
                    f"No traits data found for species: {self.scientific_name}"
                )
                return None
            logger.info(
                f"Found traits data for species: {self.scientific_name}. Data: {leptraits_data}"
            )
            return leptraits_data
        except Exception as e:
            logger.error(
                f"Error fetching traits for species {self.scientific_name}: {e}",
                exc_info=True,
            )
            return None


class SpeciesSimilarity:
    """
    A class to handle species similarity search operations.
    """

    def __init__(self, request: Request):
        """
        Initialize the SpeciesSimilarity class.
        Args:
            request (Request): The FastAPI request object.
        """
        self.request = request

    def find_similar_species(
        self, species_name: str, limit: int = 20
    ) -> list[dict] | None:
        """
        Find species similar to the given species name using image similarity.

        Args:
            species_name (str): The species name to find similar species for.
            limit (int): The maximum number of similar species to return.

        Returns:
            list[LanceSchema] | None: A
            list of dicts with keys: imgId, species, distance (smaller = more similar),
            or None if no similar species were found.
        similar_images: list[dict] = (
                ImagePersistData(
                    lance_db=self.request.app.state.lance_db
                ).find_similar_images(
                    species_name=species_name,
                    limit=limit,
                )
                or []
            )
        """
        # Get image ID for the species
        try:
            image_ids = self._get_image_ids_for_species(species_name)
            if image_ids is None:
                logger.info(
                    f"No image IDs found for species: {species_name}"
                )
                return None
            similar_images: pl.DataFrame = ImagePersistData(
                lance_db=self.request.app.state.lance_db,
                duckdb=self.request.app.state.duck_db,
            ).find_similar_images(
                image_ids=image_ids,
                limit=limit,
            )
            if similar_images is None or len(similar_images) == 0:
                logger.info(
                    f"No similar species found for species: {species_name}"
                )
                return None
            similar_images = self._filter_similar_images(
                similar_images, species_name
            )
            return similar_images.to_dicts()
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return []

    def _filter_similar_images(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
    ) -> pl.DataFrame:
        """
        Filter out images that belong to the same species as the query species.

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
            species_name (str): The species name to filter out.
        Returns:
            pl.DataFrame: Filtered DataFrame with images not belonging to the query species.
        """
        filtered_images = similar_images.filter(
            pl.col("species").str.to_lowercase().replace(" ", "_")
            != species_name.lower().replace(" ", "_")
        )
        return filtered_images

    def _get_image_ids_for_species(
        self, species_name: str
    ) -> list[str] | None:
        try:
            meta_service = ImageMetaService(
                duckdb=self.request.app.state.duck_db
            )
            image_meta = meta_service.get_image_meta_by_species(
                species=species_name
            )
            if image_meta is None or len(image_meta) == 0:
                logger.info(
                    f"No images found for species: {species_name}"
                )
                return None
            # Need to remove .png extension if present
            return [
                meta.img_id.removesuffix(".png")
                for meta in image_meta
            ]
        except Exception as e:
            logger.error(
                f"Error fetching image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return None
