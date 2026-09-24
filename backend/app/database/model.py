import logging
import os
import re

from typing import Optional, Annotated, List
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from lancedb.pydantic import LanceModel, Vector

from ..services import clip, unicom

logger = logging.getLogger(__name__)

MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]

# Mapping from CSV column names to model attributes
# It is more descriptive than the original column names
# in the consensus LepTrait dataset.
# The mapping is sourced from the records.csv file in the LepTrait dataset.
LEPTRAIT_MAPPING = {
    "WS_L_Fem": "wingspan_lower_female",
    "WS_U_Fem": "wingspan_upper_female",
    "WS_L_Mal": "wingspan_lower_male",
    "WS_U_Mal": "wingspan_upper_male",
    "WS_L": "wingspan_lower_unspecified",
    "WS_U": "wingspan_upper_unspecified",
    "FW_L_Fem": "forewing_lower_female",
    "FW_U_Fem": "forewing_upper_female",
    "FW_L_Mal": "forewing_lower_male",
    "FW_U_Mal": "forewing_upper_male",
    "FW_L": "forewing_lower_unspecified",
    "FW_U": "forewing_upper_unspecified",
    "Jan": "jan_adult_presence",
    "Feb": "feb_adult_presence",
    "Mar": "mar_adult_presence",
    "Apr": "apr_adult_presence",
    "May": "may_adult_presence",
    "Jun": "jun_adult_presence",
    "Jul": "jul_adult_presence",
    "Aug": "aug_adult_presence",
    "Sep": "sep_adult_presence",
    "Oct": "oct_adult_presence",
    "Nov": "nov_adult_presence",
    "Dec": "dec_adult_presence",
    "FlightDuration": "flight_duration",
    "DiapauseStage": "diapause_stage",
    "Voltinism": "voltinism",
    "OvipositionStyle": "oviposition_style",
    "CanopyAffinity": "canopy_affinity",
    "EdgeAffinity": "edge_affinity",
    "MoistureAffinity": "moisture_affinity",
    "DisturbanceAffinity": "disturbance_affinity",
    "NumberOfHostplantFamilies": "number_of_hostplant_families",
    "SoleHostplantFamily": "sole_hostplant_family",
    "PrimaryHostplantFamily": "primary_hostplant_family",
    "SecondaryHostplantFamily": "secondary_hostplant_family",
    "EqualHostplantFamily": "equal_hostplant_family",
    "NumberOfHostplantAccounts": "number_of_hostplant_accounts",
    "DateCreated": "date_created",
}

UnicomVector = Annotated[List[float], Vector(unicom.get_unicom_ndims())]
ClipVector = Annotated[List[float], Vector(clip.get_clip_ndims())]


class LanceSchema(LanceModel):
    """Schema for images with CLIP/UNICOM embeddings and file path reference.

    Fields:
        img_id: Unique image identifier.
        img_path: Path to the processed WebP image file on disk.
        clip_embeddings: CLIP embedding vector.
        unicom_embeddings: UNICOM embedding vector.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    img_path: str
    # species: str
    clip_embeddings: ClipVector
    unicom_embeddings: UnicomVector


class ImageMetadata(BaseModel):
    path: str

    @property
    def image_filename(self):
        return os.path.basename(self.path)

    @property
    def species_folder(self):
        return os.path.basename(os.path.dirname(self.path))

    @property
    def unique_id(self):
        return f"{self.species_folder}_{self.image_filename}"

    def to_dict(self):
        return {
            "species_folder": self.species_folder,
            "image_filename": self.image_filename,
        }

    def from_dict(cls, data: dict):
        return cls(path=os.path.join(data["species_folder"], data["image_filename"]))

    def __repr__(self):
        return f"ImageMetadata(species_folder={self.species_folder}, image_filename={self.image_filename})"


class ImageData(BaseModel):
    embedding: list[float]
    metadata: ImageMetadata

    def __repr__(self):
        return f"ImageData(unique_id={self.metadata.unique_id}, embedding={self.embedding}, metadata={self.metadata})"


# Ranks rendered by the classification panel, coarsest first.
COL_RANK_ORDER = (
    "kingdom",
    "phylum",
    "subphylum",
    "class",
    "subclass",
    "order",
    "suborder",
    "superfamily",
    "family",
    "subfamily",
    "tribe",
    "subtribe",
    "genus",
    "subgenus",
    "species",
)


_SUBGENUS_PARENTHETICAL = re.compile(r"\(([^)]*)\)")


def subgenus_name(value: str) -> str:
    """Reduce ``Genus (Subgenus)`` to the subgenus alone.

    CoL writes zoological subgenus usages with the genus in front and the
    subgenus in parentheses. Only the parenthesised part names the subgenus,
    and the genus already has its own row in the classification panel.
    """

    match = _SUBGENUS_PARENTHETICAL.search(value)
    return match.group(1).strip() if match else value


# The private spelling every existing caller uses. Kept so promoting this to
# the public API of the module did not have to touch them.
_subgenus_name = subgenus_name


def binomial_name(value: str) -> str:
    """Drop a parenthesised subgenus from a species name.

    Catalogue of Life writes zoological species usages with the subgenus
    between the genus and the epithet — `Danaus (Danaus) plexippus`. The
    subgenus has a row of its own in the classification, so repeating it
    inside the name only makes the name harder to read and harder to line up
    against the binomial every other part of the application keys on.

    A subspecies keeps its third epithet; only the parenthetical goes.
    """

    return " ".join(_SUBGENUS_PARENTHETICAL.sub(" ", value).split())


class ColTaxonomy(BaseModel):
    """A Catalogue of Life classification for one taxon.

    Replaces the GBIF-shaped SpeciesTaxonomy. Two differences matter:

    * CoL supplies the intermediate ranks GBIF never did (subphylum, subclass,
      suborder, superfamily, subfamily, tribe, subtribe, subgenus). They are
      optional because CoL populates them unevenly across groups.
    * There is no conservation status. CoL does not publish IUCN categories.

    When the queried name is a synonym, ``inputName`` keeps what was asked for
    and the remaining fields describe the accepted taxon it resolves to.
    """

    colId: str | None = None
    scientificName: str = ""
    inputName: str | None = None
    acceptedName: str | None = None
    acceptedRank: str | None = None
    authorship: str = ""
    taxonomicStatus: str = ""
    vernacularName: str = ""

    kingdom: str = ""
    phylum: str = ""
    subphylum: str | None = None
    # `class` is a Python keyword, so the field is declared under an alias and
    # must be dumped `by_alias=True` to reach the frontend as `class`.
    taxonClass: str = Field("", alias="class")
    subclass: str | None = None
    order: str = ""
    suborder: str | None = None
    superfamily: str | None = None
    family: str = ""
    subfamily: str | None = None
    tribe: str | None = None
    subtribe: str | None = None
    genus: str = ""
    subgenus: str | None = None
    species: str = ""

    extinct: bool | None = None
    environment: str | None = None
    colLink: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_row(cls, row: dict, *, input_name: str | None = None) -> "ColTaxonomy":
        """Build a payload from a col_taxonomy row joined to col_vernacular."""

        # Empty strings read better than nulls for the always-shown ranks;
        # the optional intermediate ranks stay None so the UI can omit the row.
        def text(key: str) -> str:
            value = row.get(key)
            return "" if value is None else str(value).strip()

        def optional(key: str) -> str | None:
            value = text(key)
            return value or None

        rank = text("taxon_rank")
        scientific_name = text("scientific_name")
        # CoL genus usages have no epithet, so `species` is only meaningful at
        # species rank or below. The subgenus is stripped here rather than in
        # each view: this field is a name to show a reader, and the subgenus
        # already has its own row below.
        at_species_rank = rank in ("species", "subspecies")
        species = binomial_name(scientific_name) if at_species_rank else ""
        # The name a reader sees for the taxon itself. Cleaned at species rank
        # for the same reason as `species`; left alone above it, where a
        # parenthetical is the subgenus usage's own name rather than noise
        # inside somebody else's.
        display_name = (
            binomial_name(scientific_name) if at_species_rank else scientific_name
        )

        # CoL's denormalized lineage excludes the usage's own rank: a genus row
        # carries family and above but leaves `genus` empty. Backfill it so a
        # genus or family lookup names itself.
        self_ranks = {rank: scientific_name} if rank in COL_RANK_ORDER else {}

        def ranked(key: str) -> str:
            return text(key) or self_ranks.get(key, "")

        def ranked_optional(key: str) -> str | None:
            return ranked(key) or None

        return cls(
            colId=optional("usage_id"),
            scientificName=scientific_name,
            inputName=input_name,
            acceptedName=display_name,
            acceptedRank=optional("taxon_rank"),
            authorship=text("authorship"),
            taxonomicStatus=text("status"),
            vernacularName=text("vernacular_name"),
            kingdom=ranked("kingdom"),
            phylum=ranked("phylum"),
            subphylum=ranked_optional("subphylum"),
            taxonClass=ranked("class"),
            subclass=ranked_optional("subclass"),
            order=ranked("order"),
            suborder=ranked_optional("suborder"),
            superfamily=ranked_optional("superfamily"),
            family=ranked("family"),
            subfamily=ranked_optional("subfamily"),
            tribe=ranked_optional("tribe"),
            subtribe=ranked_optional("subtribe"),
            genus=ranked("genus"),
            subgenus=_subgenus_name(ranked("subgenus")) or None,
            species=species,
            extinct=cls._to_bool(row.get("extinct")),
            environment=optional("environment"),
            colLink=optional("col_link"),
        )

    @staticmethod
    def _to_bool(value: object) -> bool | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes")

    def __repr__(self):
        return (
            f"ColTaxonomy(colId={self.colId}, scientificName={self.scientificName}, "
            f"rank={self.acceptedRank}, family={self.family}, "
            f"status={self.taxonomicStatus})"
        )


_YEAR = re.compile(r"(1[5-9]\d\d|20\d\d)")


def _row_text(row: dict, key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def year_from(value: str | None) -> int | None:
    """The first plausible publication year in a string, e.g. an authorship."""
    match = _YEAR.search(value or "")
    return int(match.group(1)) if match else None


class ColReference(BaseModel):
    """A bibliographic reference from the CoL release."""

    citation: str
    year: int | None = None
    doi: str | None = None
    link: str | None = None

    @classmethod
    def from_row(cls, row: dict, prefix: str) -> "ColReference | None":
        """Read the `{prefix}*` columns of a row joined to col_reference.

        ColDP fills `citation` for most references, but not all; the parts it
        is built from are the fallback, so a reference with a title still
        reads as one.
        """

        def get(key: str) -> str | None:
            return _row_text(row, f"{prefix}{key}")

        issued = get("issued")
        citation = get("citation")
        if not citation:
            parts = [
                get("author"),
                f"({issued})" if issued else None,
                get("title"),
                get("container_title"),
                get("volume"),
                get("page"),
            ]
            citation = " ".join(part for part in parts if part) or None
        doi = get("doi")
        link = get("link") or (f"https://doi.org/{doi}" if doi else None)
        # CoL citations often end with the same URL the reference links to,
        # which the page already renders as a link of its own.
        if citation and link and citation.endswith(link):
            stripped = citation[: -len(link)].rstrip(" .")
            citation = f"{stripped}." if stripped else None
        if not citation and not link:
            return None
        return cls(
            citation=citation or link or "",
            year=year_from(issued) or year_from(citation),
            doi=doi,
            link=link,
        )


class ColNameUsage(BaseModel):
    """One name a species has been published or recorded under."""

    colId: str | None = None
    name: str
    authorship: str | None = None
    rank: str | None = None
    status: str
    isAccepted: bool = False
    # The original combination the accepted name was based on.
    isBasionym: bool = False
    # The name the collection recorded, when CoL does not list it.
    isRecorded: bool = False
    nameStatus: str | None = None
    publishedIn: ColReference | None = None
    publishedInPage: str | None = None
    year: int | None = None


class ColTypeSpecimen(BaseModel):
    """A type specimen from the CoL TypeMaterial table."""

    status: str
    # The name this specimen typifies; often the original combination rather
    # than the accepted name.
    typifiedName: str | None = None
    citation: str | None = None
    institutionCode: str | None = None
    catalogNumber: str | None = None
    sex: str | None = None
    country: str | None = None
    locality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: str | None = None
    collector: str | None = None
    date: str | None = None
    host: str | None = None
    link: str | None = None
    remarks: str | None = None
    reference: ColReference | None = None
    referencePage: str | None = None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        try:
            return float(value) if value else None
        except ValueError:
            return None

    @classmethod
    def from_row(cls, row: dict) -> "ColTypeSpecimen":
        def get(key: str) -> str | None:
            return _row_text(row, key)

        return cls(
            status=(get("status") or "unspecified").lower(),
            typifiedName=get("typified_name"),
            citation=get("citation"),
            institutionCode=get("institution_code"),
            catalogNumber=get("catalog_number"),
            sex=get("sex"),
            country=get("country"),
            locality=get("locality"),
            latitude=cls._to_float(get("latitude")),
            longitude=cls._to_float(get("longitude")),
            altitude=get("altitude"),
            collector=get("collector"),
            date=get("collection_date"),
            host=get("host"),
            link=get("link"),
            remarks=get("remarks"),
            reference=ColReference.from_row(row, "ref_"),
            referencePage=get("page"),
        )


class ColNomenclature(BaseModel):
    """Where the accepted name comes from."""

    acceptedName: str
    authorship: str | None = None
    nameStatus: str | None = None
    # The basionym, when CoL links one and it differs from the accepted name.
    originalCombination: str | None = None
    originalAuthorship: str | None = None
    # True when the accepted name is itself the original combination; None
    # when CoL cannot say (a recombined name with no basionym linked).
    isOriginalCombination: bool | None = None
    originalPublication: ColReference | None = None
    originalPublicationPage: str | None = None
    year: int | None = None


class ColTaxonomyDetail(BaseModel):
    """Everything the species taxonomy tab renders."""

    classification: ColTaxonomy
    nomenclature: ColNomenclature
    nameUsages: list[ColNameUsage]
    typeMaterial: list[ColTypeSpecimen]
    # False when the database predates the type-material and reference
    # tables, so empty lists mean "not loaded" rather than "none recorded".
    detailAvailable: bool = True


class LepTraitData(BaseModel):
    wingspan_lower_female: Optional[float]
    wingspan_upper_female: Optional[float]
    wingspan_lower_male: Optional[float]
    wingspan_upper_male: Optional[float]
    wingspan_lower_unspecified: Optional[float]
    wingspan_upper_unspecified: Optional[float]
    forewing_lower_female: Optional[float]
    forewing_upper_female: Optional[float]
    forewing_lower_male: Optional[float]
    forewing_upper_male: Optional[float]
    forewing_lower_unspecified: Optional[float]
    forewing_upper_unspecified: Optional[float]
    jan_adult_presence: Optional[str]
    feb_adult_presence: Optional[str]
    mar_adult_presence: Optional[str]
    apr_adult_presence: Optional[str]
    may_adult_presence: Optional[str]
    jun_adult_presence: Optional[str]
    jul_adult_presence: Optional[str]
    aug_adult_presence: Optional[str]
    sep_adult_presence: Optional[str]
    oct_adult_presence: Optional[str]
    nov_adult_presence: Optional[str]
    dec_adult_presence: Optional[str]
    flight_duration: Optional[int]
    diapause_stage: Optional[str]
    voltinism: Optional[str]
    oviposition_style: Optional[str]
    canopy_affinity: Optional[str]
    edge_affinity: Optional[str]
    moisture_affinity: Optional[str]
    disturbance_affinity: Optional[str]
    number_of_hostplant_families: Optional[int]
    sole_hostplant_family: Optional[str]
    primary_hostplant_family: Optional[str]
    secondary_hostplant_family: Optional[str]
    equal_hostplant_family: Optional[str]
    number_of_hostplant_accounts: Optional[int]
    date_created: Optional[str]

    @classmethod
    def from_data(cls, row: dict):
        """
        Create a LepTraitModel instance from a CSV row.
        The row should contain keys that match the LEPTRAIT_MAPPING.
        The values will be converted to the appropriate types based on the mapping.
        If a value is "NA", "null", or an empty string, it will be set to None.
        The presence values will be decoded to descriptive strings: Absent, Present, Unknown

        :param row: A dictionary representing a row from the LepTrait CSV file.
        :return: An instance of LepTraitModel with the mapped values.
        """
        kwargs = {}

        for k_csv, k_model in LEPTRAIT_MAPPING.items():
            val = row.get(k_csv)
            # Convert types if needed
            if k_model.startswith("wingspan") or k_model.startswith("forewing"):
                kwargs[k_model] = cls._to_float(val)
            elif k_model.endswith("_presence") or k_model in [
                "flight_duration",
                "number_of_hostplant_families",
                "number_of_hostplant_accounts",
            ]:
                kwargs[k_model] = cls._to_int(val)
            else:
                kwargs[k_model] = val if val not in ["NA", "null", ""] else None
        # Decode presence values
        for month in MONTHS:
            presence_key = f"{month}_adult_presence"
            kwargs[presence_key] = cls._to_present_absent(kwargs.get(presence_key))
        return cls(**kwargs)

    def summarize(self):
        """
        Merge data into a single text removing None values.
        """
        summary = []
        for key, value in vars(self).items():
            if value is not None:
                summary.append(f"{key}: {value}")
        return "\n".join(summary)

    @staticmethod
    def _to_present_absent(value: Optional[int]) -> Optional[str]:
        """
        Decode presence integer to a descriptive string.
        """
        if value is None:
            return None
        elif value == 0:
            return "Absent"
        elif value == 1:
            return "Present"
        else:
            return "Unknown"

    @staticmethod
    def _to_float(value: Optional[str]) -> Optional[float]:
        """
        Convert string to float, handling None, empty strings, and 'NA'/'null'.
        """
        if value is None or value == "" or value in ["NA", "null"]:
            return None
        try:
            return float(value)
        except ValueError:
            logger.error(f"Failed to convert {value} to float")
            return None

    @staticmethod
    def _to_int(value: Optional[str]) -> Optional[int]:
        """
        Convert string to integer, handling None and empty strings.
        """
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            logger.error(f"Failed to convert {value} to int")
            return None


class UmapEmbedding(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    umap_x: float
    umap_y: float
    lat: Optional[float]
    lon: Optional[float]
    class_dv: Optional[str]
    cluster_label: Optional[int]
    # The specimen record behind the point, as the distribution map shows it.
    # Null until the provenance, institution and coordinate tables exist.
    source_db: str | None = None
    catalog_number: str | None = None
    institution_code: str | None = None
    institution_name: str | None = None
    validation_status: str | None = None
    recorded_country: str | None = None
    recorded_adm1: str | None = None
    reference_country: str | None = None
    reference_adm1: str | None = None

    def __repr__(self):
        return f"UmapEmbedding(species={self.species}, umap_x={self.umap_x}, umap_y={self.umap_y})"


class UmapData(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    species: str
    cluster_counts: int
    umap_embeddings: list[UmapEmbedding]

    def __repr__(self):
        return f"UmapData(species={self.species}, umap_embeddings_count={len(self.umap_embeddings)})"


class ImageMetadata(BaseModel):
    """
    Metadata for an image file.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    species: str
    source_db: str
    collection_id: str | None = None
    # Dorso ventral view of the image: dorsal or ventral
    class_dv: str
