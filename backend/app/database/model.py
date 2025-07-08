from pydantic import BaseModel
import os
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


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
            taxonomicStatus=data.get("taxonomicStatus", "Unknown"),
        )

    def __repr__(self):
        return (
            f"SpeciesTaxonomy(kingdom={self.kingdom}, phylum={self.phylum}, "
            f"class_={self.class_}, order={self.order}, family={self.family}, "
            f"genus={self.genus}, species={self.species}, scientificName={self.scientificName}, "
            f"vernacularName={self.vernacularName}, redlistCategory={self.redlistCategory})"
        )
