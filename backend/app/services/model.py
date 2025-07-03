from pydantic import BaseModel
import os
from pydantic import BaseModel, Field


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
    gbif_key: int | None = Field(None, alias="key")
    kingdom: str = Field(..., alias="kingdom")
    phylum: str = Field(..., alias="phylum")
    class_: str = Field("", alias="class")
    order: str = Field(..., alias="order")
    family: str = Field(..., alias="family")
    genus: str = Field(..., alias="genus")
    species: str = Field("", alias="species")
    scientific_name: str = Field("", alias="scientificName")
    vernacular_name: str = Field("", alias="vernacularName")
    redlist_category: str = Field("Unknown", alias="redlistCategory")

    @classmethod
    def from_json(cls, data: dict, redlist_category: str = "Unknown"):
        return cls(
            gbif_key=data.get("key", None),
            kingdom=data.get("kingdom", ""),
            phylum=data.get("phylum", ""),
            class_=data.get("class", ""),
            order=data.get("order", ""),
            family=data.get("family", ""),
            genus=data.get("genus", ""),
            species=data.get("species", ""),
            scientific_name=data.get("scientificName", ""),
            vernacular_name=data.get("vernacularName", ""),
            redlist_category=redlist_category,
        )

    def __repr__(self):
        return (
            f"SpeciesTaxonomy(kingdom={self.kingdom}, phylum={self.phylum}, "
            f"class_={self.class_}, order={self.order}, family={self.family}, "
            f"genus={self.genus}, species={self.species}, scientific_name={self.scientific_name}, "
            f"vernacular_name={self.vernacular_name}, redlist_category={self.redlist_category})"
        )
