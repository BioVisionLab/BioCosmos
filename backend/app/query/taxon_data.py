from app.services.metadata import ImageMetaStats
from app.services.metadata import ImageMetaService
import logging

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..services.images import ImagePersistData
from ..services.leptraits import LepTraits
from ..services.col import ColTaxonSearch
from ..services.gbif import GbifPersistData
from ..services.institution import InstitutionDirectory
from ..services.openai import AiSummary
from ..services.taxonomy_update import TaxonomyValidationStats


logger = logging.getLogger(__name__)


class InstitutionInfo(BaseModel):
    """The resolved name behind an institutionCodes key; see instharmonize."""

    name: str
    homepage: str | None = None
    country: str | None = None
    source: str


class TaxonStatPayload(BaseModel):
    """
    A class to represent taxon statistics from GBIF and LepTraits entries.
    """

    gbifEntries: int
    lepTraitsEntries: int
    imageEntries: int
    familyCount: int
    familyCountValidated: int
    speciesCount: int
    sourceDbCount: dict[str, int] | None
    entriesByFamily: dict | None
    entriesByFamilyValidated: dict | None
    institutionCounts: dict[str, int] | None
    institutionDirectory: dict[str, InstitutionInfo] = {}
    topTenSpecies: dict | None

    @classmethod
    def from_data(
        cls,
        gbif_entries: int | None,
        lep_traits_entries: int | None,
        image_entries: int | None,
        family_count: int | None,
        family_count_validated: int | None,
        species_count: int | None,
        source_db_count: dict[str, int] | None,
        entries_by_family: dict | None,
        entries_by_family_validated: dict | None,
        institution_counts: dict[str, int] | None,
        top_ten_species: dict | None,
        institution_directory: dict[str, dict] | None = None,
    ):
        """
        Create a TaxonStatPayload instance from the provided data.

        Args:
            gbif_entries (int): The number of entries in the GBIF data table.
            lep_traits_entries (int): The number of entries in the Leptraits.
            image_entries (int): The number of image entries
            family_count (int): The number of distinct recorded families.
            family_count_validated (int): The number of distinct families
                resolved with confidence by the taxonomy harmonization,
                excluding unresolved (ambiguous or unmatched) occurrences.
            gbif_species_count (int): The number of unique GBIF species in the occurrence
            institution_counts (dict): Image counts per holding institution.
            institution_directory (dict): Full name and website per
                institution code, for the codes that could be resolved.

        Returns:
            TaxonStatPayload: An instance of TaxonStatPayload.
        """
        return cls(
            gbifEntries=gbif_entries if gbif_entries is not None else 0,
            lepTraitsEntries=lep_traits_entries
            if lep_traits_entries is not None
            else 0,
            imageEntries=image_entries if image_entries is not None else 0,
            familyCount=family_count if family_count is not None else 0,
            familyCountValidated=family_count_validated
            if family_count_validated is not None
            else 0,
            speciesCount=species_count if species_count is not None else 0,
            sourceDbCount=source_db_count if source_db_count is not None else {},
            entriesByFamily=entries_by_family if entries_by_family is not None else {},
            entriesByFamilyValidated=entries_by_family_validated
            if entries_by_family_validated is not None
            else {},
            institutionCounts=institution_counts
            if institution_counts is not None
            else {},
            institutionDirectory={
                code: InstitutionInfo(**info)
                for code, info in (institution_directory or {}).items()
            },
            topTenSpecies=top_ten_species if top_ten_species is not None else {},
        )


class SpeciesPayload(BaseModel):
    """
    A class to represent a species payload for search operations.
    It includes the species taxonomy and traits data.
    """

    speciesId: str
    taxonomy: dict
    traits: dict | None = None

    @classmethod
    def from_data(
        cls,
        species_id: str,
        taxonomy: dict,
        traits: dict | None,
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
        )


class SimilarSpeciesPayload(BaseModel):
    """
    A class to represent similar species data.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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


class RankScopedSearch:
    """Resolve a name that must sit at one taxonomic rank.

    The GBIF version searched by name and then scanned the returned payload for
    a key whose value equalled the query, which quietly accepted a genus hit for
    a family lookup. The CoL backbone can be asked for the rank directly.
    """

    rank: str = ""

    def __init__(self, request: Request, query: str = ""):
        self.name = query.strip()
        self.request = request

    async def get_classification(self) -> list[dict]:
        """Return the CoL classification for this name at this rank."""
        if not self.name:
            return []
        try:
            service = ColTaxonSearch(duckdb=self.request.app.state.duck_db)
            classification = await service.search_at_rank(self.name, self.rank)
            if not classification:
                logger.info(f"No CoL data found for {self.rank}: {self.name}")
                return []
            payload = ClassificationPayload.from_data(
                matched_category=self.rank,
                classification=classification,
            )
            return [payload.model_dump()]
        except Exception as e:
            logger.error(
                f"Error fetching classification for {self.rank}: {e}", exc_info=True
            )
            return []


class OrderSearch(RankScopedSearch):
    """Order-level taxon search against the CoL backbone."""

    rank = "order"


class FamilySearch(RankScopedSearch):
    """Family-level taxon search against the CoL backbone."""

    rank = "family"


class GenusSearch(RankScopedSearch):
    """Genus-level taxon search against the CoL backbone."""

    rank = "genus"


class SpeciesSearch(RankScopedSearch):
    """Species-level taxon search against the CoL backbone.

    Species name = genus + specificEpithet.
    """

    rank = "species"

    def __init__(self, request: Request, genus: str = "", specific_epithet: str = ""):
        super().__init__(
            request=request,
            query=f"{genus.strip()} {specific_epithet.strip()}".strip(),
        )


class TaxonSearch:
    """
    A class to handle taxon search operations against the CoL backbone.
    """

    def __init__(self, request: Request, query: str = ""):
        """
        Initialize the TaxonSearch class.
        Args:
            query (str): The species name to search for.
        """
        self.scientific_name = query.strip().lower()
        if "_" in self.scientific_name:
            self.scientific_name = self.scientific_name.replace("_", " ").strip()
        self.request = request

    def get_counts(self) -> dict | None:
        """
        Get the counts of species in each taxon.
        """
        gbif_service = GbifPersistData(duckdb=self.request.app.state.duck_db)
        leptraits_service = LepTraits(duckdb=self.request.app.state.duck_db)
        img_meta_stats = ImageMetaStats(duckdb=self.request.app.state.duck_db)
        taxonomy_validation = TaxonomyValidationStats(
            duckdb_client=self.request.app.state.duck_db
        )
        try:
            counts_gbif: int | None = gbif_service.count_entries()
            count_leptrait: int | None = leptraits_service.count_entries()
            count_img: int | None = img_meta_stats.get_entries_count()
            count_families: int | None = img_meta_stats.get_family_count()
            count_families_validated: int | None = (
                taxonomy_validation.get_validated_family_count()
            )
            count_species: int | None = img_meta_stats.get_species_count()
            source_db_count: dict[str, int] | None = img_meta_stats.get_source_db_count()
            entries_by_family: dict[str, int] | None = img_meta_stats.count_images_per_family()
            entries_by_family_validated: dict[str, int] | None = (
                taxonomy_validation.count_images_per_validated_family()
            )
            institution_counts: dict[str, int] | None = (
                img_meta_stats.get_institution_counts()
            )
            top_ten_species: dict | None = img_meta_stats.get_top_ten_species()
            institution_directory = InstitutionDirectory(
                self.request.app.state.duck_db
            ).get_all()

            payload = TaxonStatPayload.from_data(
                gbif_entries=counts_gbif,
                lep_traits_entries=count_leptrait,
                image_entries=count_img,
                family_count=count_families,
                family_count_validated=count_families_validated,
                species_count=count_species,
                source_db_count=source_db_count,
                entries_by_family=entries_by_family,
                entries_by_family_validated=entries_by_family_validated,
                institution_counts=institution_counts,
                top_ten_species=top_ten_species,
                institution_directory=institution_directory,
            )
            return payload.model_dump()
        except Exception as e:
            logger.error(f"Error fetching counts: {e}", exc_info=True)
            return None

    async def search(self) -> dict | None:
        """
        Search for species taxonomy data in the Catalogue of Life backbone.

        Args:
            query (str): The species name to search for.

        Returns:
            dict: The species payload, or None only when no name was given.

            An unresolved name still returns a payload, with an empty
            `taxonomy`. The images, traits, specimens and literature on a
            species page do not come from CoL, and returning None here would
            take all of them down with the classification panel.
        """
        if not self.scientific_name:
            return None

        try:
            taxon_data = await self._get_taxonomy()
            trait_data = self._get_traits()
            if not taxon_data:
                logger.info(
                    f"No CoL data found for species: {self.scientific_name}; "
                    "serving the page without a classification."
                )

            payload = SpeciesPayload.from_data(
                species_id=self.scientific_name,
                taxonomy=taxon_data,
                traits=trait_data,
            )
            return payload.model_dump()

        except Exception as e:
            logger.error(f"Error searching for taxon: {e}", exc_info=True)
            return None

    async def get_classification(self) -> list[dict]:
        """
        Get the taxon classification for the species from the database.

        Returns:
            list[dict]: A list of classification data or None if not found.
        """
        if not self.scientific_name:
            return []

        try:
            taxonomy = await self._get_taxonomy()
            if not taxonomy:
                logger.info(f"No CoL data found for species: {self.scientific_name}")
                return []
            # We match the query to values and keep track the key where it matched
            matched_data: list[dict] = []
            for key, value in taxonomy.items():
                if (
                    isinstance(value, str)
                    and value.lower() == self.scientific_name.lower()
                ):
                    classification_payload = ClassificationPayload.from_data(
                        matched_category=key,
                        classification=taxonomy,
                    )
                    matched_data.append(classification_payload.model_dump())
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

    async def generate_summary(self) -> str | None:
        """
        Generate a summary for the species using an AI service.

        Returns:
            str | None: The generated summary or None if not found.
        """
        if not self.scientific_name:
            return None
        try:
            taxon_data = await self._get_taxonomy()
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
                message = (
                    f"No summary could be generated for species: {self.scientific_name}"
                )
                logger.info(message)
                return None

            logger.info(f"Summary generated for species: {self.scientific_name}")
            return summary

        except Exception as e:
            logger.error(
                f"Error generating summary for species {self.scientific_name}: {e}",
                exc_info=True,
            )
            return None

    def _generate_prompt(self, taxon_data: dict, traits: dict | None) -> str:
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

    async def _get_taxonomy(self) -> dict:
        """
        Fetch the CoL classification for the species.

        Returns:
            dict: The species classification, or an empty dict if not found.
        """
        try:
            service = ColTaxonSearch(duckdb=self.request.app.state.duck_db)
            taxonomy = await service.search(self.scientific_name)
            if taxonomy is None:
                logger.info(f"No CoL data found for species: {self.scientific_name}")
                return {}
            return taxonomy
        except Exception as e:
            logger.error(
                f"Error fetching CoL data for species {self.scientific_name}: {e}",
                exc_info=True,
            )
            return {}

    def _get_traits(self) -> dict | None:
        """
        Fetch traits for the species using the LepTraits service.

        Returns:
            dict: A dictionary containing the species traits data or None if not found.
        """
        try:
            leptraits = LepTraits(duckdb=self.request.app.state.duck_db)
            leptraits_data = leptraits.get(self.scientific_name)
            if leptraits_data is None:
                logger.info(f"No traits data found for species: {self.scientific_name}")
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
