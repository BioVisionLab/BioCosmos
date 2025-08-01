# Pretrained shared embedder for CLIP model
# Handle text and image embeddings using CLIP model
import logging
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"


class ClipEmbedder:
    """Class to handle text embedding using CLIP model.

    Args:
        model (CLIPModel): The CLIP model for text embedding.
        processor (CLIPProcessor): The CLIP processor for text preprocessing.
        device (str): The device to run the model on ('cpu' or 'cuda').
    returns:
        List[float]: The normalized text embedding vector.
    """

    def __init__(self):
        self.device = (
            torch.accelerator.current_accelerator().type
            if torch.accelerator.is_available()
            else "cpu"
        )
        self.logger: logging.Logger = logger
        self.model, self.processor = self._load_model()

    def _load_model(self):
        """Load the CLIP model and processor."""
        try:
            model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(
                self.device
            )
            processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
            model.eval()
            logger.info(
                f"CLIP model {CLIP_MODEL_NAME} loaded successfully."
            )
            return model, processor
        except Exception as e:
            self.logger.error(
                f"Error loading CLIP model: {e}", exc_info=True
            )
            return None, None

    def ndims(self) -> int:
        """Get the dimensions of the CLIP model's text embeddings."""
        if self.model is None:
            self.logger.error(
                "CLIP model not available for getting dimensions."
            )
            return None
        try:
            dimensions = self.get_embedding_from_text("test")
            logger.info(
                f"CLIP model text embedding dimensions: {len(dimensions)}"
            )
            return len(dimensions)
        except Exception as e:
            self.logger.error(
                f"Error getting CLIP model dimensions: {e}",
                exc_info=True,
            )
            return None

    def get_embedding_from_img(self, img_path) -> list[float]:
        """Get the image embedding from a given image path."""
        if self.model is None:
            self.logger.error(
                "CLIP model not available for image embedding."
            )
            return None
        try:
            images = Image.open(img_path).convert("RGB")
            inputs = self.processor(
                images=images, return_tensors="pt", padding=True
            ).to(self.device)
            with torch.no_grad():
                image_features = self.model.get_image_features(
                    **inputs
                )
            image_features = image_features / image_features.norm(
                dim=-1, keepdim=True
            )  # Normalize the embeddings
            return image_features.cpu().numpy().squeeze()
        except FileNotFoundError as e:
            self.logger.error(
                f"Image file not found: {e}", exc_info=True
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Error processing image {img_path}: {e}",
                exc_info=True,
            )
            return None

    def get_embedding_from_text(self, text) -> list[float]:
        if self.model is None:
            self.logger.error(
                "CLIP model not available for text embedding."
            )
            return None
        inputs = self.processor(
            text=text,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.device)
        logger.info(f"Computing text embedding for: {text}")
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        logger.info(
            f"Text embedding computed successfully for: {text}"
        )
        return text_features.cpu().numpy().squeeze()
