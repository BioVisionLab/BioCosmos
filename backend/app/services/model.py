from pydantic import BaseModel

class ImageMetadata(BaseModel):
    species_folder: str
    image_filename: str

    def to_dict(self):
        return {
            "species_folder": self.species_folder,
            "image_filename": self.image_filename
        }

    def __repr__(self):
        return f"ImageMetadata(species_folder={self.species_folder}, image_filename={self.image_filename})"
    
class ImageData(BaseModel):
    unique_id: str
    embedding: list[float]
    metadata: ImageMetadata

    def __repr__(self):
        return f"ImageData(unique_id={self.unique_id}, embedding={self.embedding}, metadata={self.metadata})"