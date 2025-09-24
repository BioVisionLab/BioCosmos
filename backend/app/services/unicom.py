import logging
import torch
import unicom
import io
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

UNICOM_COLLECTION_NAME = "unicom_collection"
# UNICOM_COLLECTION_NAME = "biocosmos_images_unicom" # New collection for UNICOM
UNICOM_MODEL_NAME = "ViT-L/14@336px"  # UNICOM model
DEVICE = (
    torch.accelerator.current_accelerator().type
    if torch.accelerator.is_available()
    else "cpu"
)


class UnicomImageEmbedder:
    def __init__(self):
        """Initialize the UNICOM image embedder."""
        self.device = DEVICE
        self.logger = logger
        self.model, self.transform = self._load_model()

    def _load_model(self):
        """Load the UNICOM model and its transform."""
        logger.info(f"Loading UNICOM model: {UNICOM_MODEL_NAME}...")
        try:
            _model, transform = unicom.load(UNICOM_MODEL_NAME)
            model = _model.to(self.device)
            model.eval()
            logger.info(
                f"UNICOM model and transform loaded and moved to {self.device} successfully"
            )
            return model, transform
        except Exception as e:
            logger.error(
                f"Fatal error loading or moving UNICOM model: {e}",
                exc_info=True,
            )
            raise e

    def ndims(self):
        """Get the dimensions of the UNICOM model's image embeddings."""
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for getting dimensions."
            )
            return None
        try:
            # Get a dummy embedding to determine dimensions
            dummy_image = Image.new("RGB", (224, 224), color="white")
            dummy_tensor = (
                self.transform(dummy_image)
                .unsqueeze(0)
                .to(self.device)
            )
            with torch.no_grad():
                embedding = self.model(dummy_tensor)
            return embedding.shape[-1]
        except Exception as e:
            self.logger.error(
                f"Error getting UNICOM model dimensions: {e}",
                exc_info=True,
            )
            return None

    def get_embedding_from_img(self, image_path):
        """Get the image embedding from a given image path."""
        if self.model is None:
            self.logger.error(
                "UNICOM model not available for image embedding."
            )
            return None
        try:
            image: Image = Image.open(image_path).convert("RGB")
            return self._get_embedding(image)
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
            return self._get_embedding(image)
        except Exception as e:
            self.logger.error(
                f"Could not process base64 image with UNICOM: {e}",
                exc_info=True,
            )
            return None

    def _get_embedding(self, image: Image) -> np.ndarray | None:
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

    def get_collection_name(self):
        """Get the name of the UNICOM collection."""
        return UNICOM_COLLECTION_NAME
