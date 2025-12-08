import logging
import torch

from ..configs.config import EmbedderConfig
import unicom
import io
import numpy as np
from PIL import Image
from PIL.Image import Image as PILImage

logger = logging.getLogger(__name__)

UNICOM_MODEL_NAME = "ViT-L/14@336px"  # UNICOM model
MAX_UNICOM_RESOLUTION = 336


class UnicomModel:
    def __init__(self, model=None, transform=None):
        self.model = model
        self.transform = transform

    @classmethod
    def load_model(cls):
        """Load the UNICOM model and its transform."""
        try:
            config = EmbedderConfig()
            model, transform = unicom.load(UNICOM_MODEL_NAME)
            model = model.to(config.device)
            model.eval()
            logger.info(
                f"UNICOM model and transform loaded and moved to {config.device} successfully"
            )
            return model, transform
        except Exception as e:
            logger.error(
                f"Fatal error loading or moving UNICOM model: {e}",
                exc_info=True,
            )
            raise e


def get_unicom_ndims() -> int:
    """Get the dimensions of the UNICOM model's image embeddings."""
    config = EmbedderConfig()
    unicom_model, transform = UnicomModel.load_model()
    if unicom_model is None:
        logger.error(
            "UNICOM model not available for getting dimensions."
        )
        return None
    try:
        # Get a dummy embedding to determine dimensions
        dummy_image = Image.new("RGB", (224, 224), color="white")
        dummy_tensor = (
            transform(dummy_image).unsqueeze(0).to(config.device)
        )
        with torch.no_grad():
            embedding = unicom_model(dummy_tensor)
            return embedding.shape[-1]
    except Exception as e:
        logger.error(
            f"Error getting UNICOM model dimensions: {e}",
            exc_info=True,
        )
        return None


class UnicomImageEmbedder:
    def __init__(self, model, transform):
        """Initialize the UNICOM image embedder."""
        config = EmbedderConfig()
        self.device = config.device
        self.logger = logger
        self.model = model
        self.transform = transform

    def get_embedding_from_img(self, image_path):
        """Get the image embedding from a given image path."""
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for image embedding."
            )
            return None
        try:
            image: Image = Image.open(image_path).convert("RGB")
            image = self._resize_image(image)
            return self.get_embedding(image)
        except Exception as e:
            self.logger.error(
                f"Could not process image {image_path} with UNICOM: {e}",
                exc_info=True,
            )
            return None

    def get_embedding_from_bytes(self, image_bytes: bytes):
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for image embedding."
            )
            return None
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image = self._resize_image(image)
            return self.get_embedding(image)
        except Exception as e:
            self.logger.error(
                f"Could not process base64 image with UNICOM: {e}",
                exc_info=True,
            )
            return None

    def batch_get_embeddings(
        self, images: list[PILImage]
    ) -> list[np.ndarray]:
        """Get embeddings for a batch of PIL Images."""
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for image embedding."
            )
            return []
        try:
            images = [self._resize_image(img) for img in images]
            inputs = torch.stack(
                [self.transform(img) for img in images]
            ).to(self.device)
            with torch.no_grad():
                image_features = self.model(inputs)
            image_features /= image_features.norm(
                dim=-1, keepdim=True
            )
            embeddings_array = image_features.cpu().numpy()
            return [embedding for embedding in embeddings_array]
        except Exception as e:
            self.logger.error(
                f"Error processing batch of images with UNICOM: {e}",
                exc_info=True,
            )

    def get_embedding(self, image: Image) -> np.ndarray | None:
        """Get the image embedding from a given PIL Image."""
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for image embedding."
            )
            return None
        try:
            # Apply UNICOM's transform and add batch dimension
            image_tensor = (
                self.transform(image).unsqueeze(0).to(self.device)
            )

            with torch.no_grad():
                # Get UNICOM embedding
                image_features = self.model(image_tensor)

            # Normalize (important for cosine similarity)
            image_features /= image_features.norm(
                dim=-1, keepdim=True
            )
            return image_features.cpu().numpy().squeeze()
        except Exception as e:
            self.logger.error(
                f"Could not process image with UNICOM: {e}",
                exc_info=True,
            )
            return None

    def _resize_image(self, image: Image) -> Image:
        """Resize image to fit within MAX_CLIP_RESOLUTION while maintaining aspect ratio."""
        max_dimension = max(image.size)
        if max_dimension > MAX_UNICOM_RESOLUTION:
            scale = MAX_UNICOM_RESOLUTION / max_dimension
            new_size = (
                int(image.size[0] * scale),
                int(image.size[1] * scale),
            )
            return image.resize(new_size, Image.ANTIALIAS)
        return image
