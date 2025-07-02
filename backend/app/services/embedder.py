import logging
import os
import glob
from tqdm import tqdm
from .chroma import upsert_to_chroma, get_client
from enum import Enum
from .unicom import UnicomImageEmbedder, UNICOM_COLLECTION_NAME
from .clip import ClipTextEmbedder, CLIP_COLLECTION_NAME
from .model import ImageMetadata, ImageData

IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally

logger = logging.getLogger(__name__)

class ModelType(Enum):
    UNICOM = 1
    CLIP = 2

    def collection_name(self):
        """Return the collection name based on the model type."""
        if self == ModelType.UNICOM:
            return UNICOM_COLLECTION_NAME
        elif self == ModelType.CLIP:
            return CLIP_COLLECTION_NAME
        else:
            raise ValueError("Invalid model type")

class ImageEmbeddingIngestor:
    def __init__(self,  model_type, img_dir=IMAGE_BASE_DIR):
        """Initialize model and device for image embedding."""
        self.img_dir = img_dir
        self.model_type = model_type

    def get_images(self) -> list[str]:
        """Get all image paths from the specified directory."""
        if not os.path.exists(self.img_dir):
            logger.error(f"Image directory does not exist: {self.img_dir}")
            return []

        # Use glob to recursively find image files
        pattern = os.path.join(self.img_dir, '**') + '/*'
        logger.info(f"Searching for images in directory: {self.img_dir} with pattern: {pattern}")
        # Filter for common image file extensions
        # and ensure they are files (not directories)                                                               
        image_paths = [
            f for f in glob.glob(pattern, recursive=True)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')) and os.path.isfile(f)
        ]

        logger.info(f"Found {len(image_paths)} images in directory: {self.img_dir}")
        return image_paths
    
    def get_embedding(self, img_paths: list[str]) -> list[ImageData] | None:
        """Get embeddings for a list of image paths."""

        match self.model_type:
            case ModelType.UNICOM:
                logger.info(f"Getting UNICOM embeddings for {len(img_paths)} images.")
                embedding = self.embed_unicom(img_paths)
                return embedding if embedding is not None else None
                    
            case ModelType.CLIP:
                logger.info(f"Getting CLIP embeddings for {len(img_paths)} images.")
                embedding = self.embed_clip(img_paths)
                return embedding if embedding is not None else None
            
    def embed_clip(self, img_paths: list[str]) -> list[ImageData]:
        """Embed images using CLIP model."""
        logger.info(f"Found {len(img_paths)} images to embed.")
        img_data: list[ImageData] = []

        processed_image_count = 0
        skipped_image_count = 0
        clip = ClipTextEmbedder()
        total_images = len(img_paths)
        with tqdm(total=total_images, desc="Embedding images", colour="blue") as progress_bar:
            for img_path in img_paths:
                if not self.file_exists(img_path):
                    self.handle_missing_files(img_path, skipped_image_count)
                    progress_bar.update(1)
                    continue
                try:
                    embedding = clip.get_embedding_from_img(img_path)
                    if embedding is not None:
                        self.update_embedding(img_data, embedding.flatten().tolist(), img_path)
                        processed_image_count += 1
                    else:
                        skipped_image_count += 1
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}", exc_info=True)
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                
                progress_bar.update(1)

        return img_data

    def embed_unicom(self, img_paths: list[str]) -> list[ImageData]:
        """Embed images using UNICOM model."""
        logger.info(f"Found {len(img_paths)} images to embed.")

        embeddings: list[ImageData] = []
        processed_image_count = 0
        skipped_image_count = 0

        total_images = len(img_paths)
        unicom = UnicomImageEmbedder()
        
        with tqdm(total=total_images, desc="Embedding images", colour="blue") as progress_bar:
            for img_path in img_paths:
                if not self.file_exists(img_path):
                    self.handle_missing_files(img_path, skipped_image_count)
                    progress_bar.update(1)
                    continue
                try:

                    embedding = unicom.get_embedding_from_img(img_path)
                    if embedding is not None:
                        self.update_embedding(embeddings, embedding.flatten().tolist(), img_path)
                        processed_image_count += 1
                    else:
                        skipped_image_count += 1
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}", exc_info=True)
                    skipped_image_count += 1
                    progress_bar.update(1)
                    continue
                
                progress_bar.update(1)
        logger.info(f"Processed {processed_image_count} images, skipped {skipped_image_count} images.")
        return embeddings
        
    def update_embedding(self,  img_data: list[ImageData], embedding: list[float], img_path: str):
        """Update the embedding list with new embedding."""
        data = ImageData(
            embedding=embedding,
            metadata=ImageMetadata(
                path=img_path,
            )
        )
        img_data.append(data)

    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        return os.path.isfile(file_path)
    
    def handle_missing_files(self, img_path: str, skipped_count: int):
        """Log a warning if the image file does not exist."""
        if not self.file_exists(img_path):
            logger.warning(f"Image file not found: {img_path}")
            skipped_count += 1\
    
    async def filter_new_images_from_db(self, collection_name, all_images):
        """Filter out images that are already in the ChromaDB."""
        client = await get_client()
        if not client:
            logger.error("ChromaDB client is not available.")
            return all_images
        collection = client.get_collection(name=collection_name)

        new_images = []
        existing_ids = set()
        for img_path in tqdm(all_images, desc="Filtering new images", colour="blue"):
            unique_id = ImageMetadata(path=img_path).unique_id
            # Check if the image already exists in the collection
            existing = collection.get(ids=[unique_id])
            if not existing or not existing['ids']:
                # If the image does not exist, add it to the new images list
                new_images.append(img_path)
            else:
                # If the image exists, log it
                existing_ids.add(unique_id)
        logger.info(f"Image already exists in the collection: {img_path}")
        logger.info(f"New images to process: {len(new_images)}")
        return new_images

    async def process(self):
        """Main method to embed images in batches and store in ChromaDB."""
        logger.info(f"Starting CLIP image embedding process from directory: {self.img_dir}")
        collection_name: str = self.model_type.collection_name()
        image_paths = self.get_images()
        logger.info(f"Found {len(image_paths)} images to process.")
        # we only process first 50 for testing purposes
        # filter  out images that are already in the database
        image_paths = await self.filter_new_images_from_db(collection_name, image_paths)
        if not image_paths:
            logger.warning("No new images to process.")
            return
        img_data = self.get_embedding(image_paths)

        if img_data:
            await upsert_to_chroma(
                collection_name=collection_name,
                img_data=img_data
            )
            logger.info("Embedding and upsert completed successfully.")
        else:
            logger.warning("No valid images found for embedding.")