import logging
import os

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
        species: Species name (derived from directory structure).
        clip_embeddings: CLIP embedding vector.
        unicom_embeddings: UNICOM embedding vector.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    img_id: str
    img_path: str
    species: str
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
        return cls(
            path=os.path.join(
                data["species_folder"], data["image_filename"]
            )
        )

    def __repr__(self):
        return f"ImageMetadata(species_folder={self.species_folder}, image_filename={self.image_filename})"


class ImageData(BaseModel):
    embedding: list[float]
    metadata: ImageMetadata

    def __repr__(self):
        return f"ImageData(unique_id={self.metadata.unique_id}, embedding={self.embedding}, metadata={self.metadata})"


class SpeciesTaxonomy(BaseModel):
    key: int | None = Field(None, alias="key")
    kingdom: str = Field("", alias="kingdom")
    phylum: str = Field("", alias="phylum")
    taxonClass: str = Field("", alias="taxonClass")
    order: str = Field("", alias="order")
    family: str = Field("", alias="family")
    genus: str = Field("", alias="genus")
    species: str = Field("", alias="species")
    authorship: str = Field("", alias="authorship")
    vernacularName: str = Field("", alias="vernacularName")
    redlistCategory: str = Field("Unknown", alias="redlistCategory")
    taxonomicStatus: str = Field("Accepted", alias="taxonomicStatus")

    @classmethod
    def from_json(cls, data: dict, redlistCategory: str = "Unknown"):
        taxonomic_status: str = data.get(
            "taxonomicStatus", ""
        ).capitalize()

        return cls(
            key=data.get("key", None),
            kingdom=data.get("kingdom", ""),
            phylum=data.get("phylum", ""),
            taxonClass=data.get("taxonClass", ""),
            order=data.get("order", ""),
            family=data.get("family", ""),
            genus=data.get("genus", ""),
            species=data.get("species", ""),
            authorship=data.get("authorship", ""),
            vernacularName=data.get("vernacularName", ""),
            redlistCategory=redlistCategory,
            taxonomicStatus=taxonomic_status,
        )

    def __repr__(self):
        return (
            f"SpeciesTaxonomy(kingdom={self.kingdom}, phylum={self.phylum}, "
            f"class_={self.class_}, order={self.order}, family={self.family}, "
            f"genus={self.genus}, species={self.species}, scientificName={self.scientificName}, "
            f"vernacularName={self.vernacularName}, redlistCategory={self.redlistCategory})"
        )


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
            if k_model.startswith("wingspan") or k_model.startswith(
                "forewing"
            ):
                kwargs[k_model] = cls._to_float(val)
            elif k_model.endswith("_presence") or k_model in [
                "flight_duration",
                "number_of_hostplant_families",
                "number_of_hostplant_accounts",
            ]:
                kwargs[k_model] = cls._to_int(val)
            else:
                kwargs[k_model] = (
                    val if val not in ["NA", "null", ""] else None
                )
        # Decode presence values
        for month in MONTHS:
            presence_key = f"{month}_adult_presence"
            kwargs[presence_key] = cls._to_present_absent(
                kwargs.get(presence_key)
            )
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
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    img_id: str
    umap_x: float
    umap_y: float
    lat: Optional[float]
    lon: Optional[float]
    class_dv: Optional[str]
    cluster_label: Optional[int]

    def __repr__(self):
        return f"UmapEmbedding(species={self.species}, umap_x={self.umap_x}, umap_y={self.umap_y})"


class UmapData(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    species: str
    cluster_counts: int
    umap_embeddings: list[UmapEmbedding]

    def __repr__(self):
        return f"UmapData(species={self.species}, umap_embeddings_count={len(self.umap_embeddings)})"


class ImageMetadata(BaseModel):
    """
    Metadata for an image file.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    img_id: str
    species: str
    source_db: str
    collection_id: str | None = None
    # Dorso ventral view of the image: dorsal or ventral
    class_dv: str
