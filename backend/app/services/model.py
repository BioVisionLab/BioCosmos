from pydantic import BaseModel
import os


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


class SpeciesTaxonomy:
    def __init__(
        self,
        kingdom: str,
        phylum: str,
        class_: str,
        order: str,
        family: str,
        genus: str,
        species: str,
        scientific_name,
        vernacular_name: str = "",  # Optional vernacular name, defaults to species name
    ):
        self.kingdom = kingdom
        self.phylum = phylum
        self.class_ = class_
        self.order = order
        self.family = family
        self.genus = genus
        self.species = species
        self.scientific_name = scientific_name
        self.vernacular_name = vernacular_name

    def from_json(cls, data: dict):
        return cls(
            kingdom=data.get("kingdom", ""),
            phylum=data.get("phylum", ""),
            class_=data.get("class", ""),
            order=data.get("order", ""),
            family=data.get("family", ""),
            genus=data.get("genus", ""),
            species=data.get("species", ""),
            scientific_name=data.get("scientificName", ""),
            vernacular_name=data.get("vernacularName", ""),
        )

    def __repr__(self):
        return f"SpeciesTaxonomy(name={self.name}, rank={self.rank}, kingdom={self.kingdom}, phylum={self.phylum}, class_={self.class_}, order={self.order}, family={self.family}, genus={self.genus})"
