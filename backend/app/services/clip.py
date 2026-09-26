import logging
import numpy as np
import torch
import os

from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from PIL.Image import Image as PILImage

from ..configs.config import EmbedderConfig

os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
MAX_CLIP_RESOLUTION = 512
EMBED_DIM = 512


class ClipModel:
    """Class to handle loading of CLIP model and processor."""

    def __init__(self, model=None, processor=None):
        self.model = model
        self.processor = processor

    @classmethod
    def load_model(cls):
        """Load the CLIP model and processor."""
        config = EmbedderConfig()
        try:
            # transformers wraps `to` with functools.wraps, which the stubs
            # expose as an unbound `_Wrapped` that pyright cannot bind `self` to.
            model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(
                config.device  # pyright: ignore[reportArgumentType]
            )
            processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
            model.eval()
            logger.info(
                f"CLIP model {CLIP_MODEL_NAME} loaded successfully."
            )
            return model, processor
        except Exception as e:
            logger.error(
                f"Error loading CLIP model: {e}", exc_info=True
            )
            return None, None


def projected_features(output) -> "torch.Tensor":
    """The projected embedding, however transformers chose to wrap it.

    transformers 5 changed `get_text_features` and `get_image_features` to
    return a `BaseModelOutputWithPooling` whose `pooler_output` carries the
    projection; 4.x returned that tensor directly. Accepting both keeps the
    pinned version free to move without search silently returning nothing —
    which is how this surfaced: the normalization below raised
    `'BaseModelOutputWithPooling' object has no attribute 'norm'`, the caller
    logged it, and every query came back empty.
    """
    pooled = getattr(output, "pooler_output", None)
    return output if pooled is None else pooled


def get_clip_ndims() -> int:
    """Get the dimensions of the CLIP model's text embeddings."""
    # Hardcoded to 512 for openai/clip-vit-base-patch32 to avoid loading the model during import
    return EMBED_DIM


class ClipEmbedder:
    """Class to handle text embedding using CLIP model.

    Args:
        model (CLIPModel): The CLIP model for text embedding.
        processor (CLIPProcessor): The CLIP processor for text preprocessing.
        device (str): The device to run the model on ('cpu' or 'cuda').
    returns:
        List[float]: The normalized text embedding vector.
    """

    def __init__(self, model, processor):
        self.logger: logging.Logger = logger
        config = EmbedderConfig()
        self.device = config.device
        self.model = model
        self.processor = processor

    def get_embedding_from_img(self, img_path) -> np.ndarray | None:
        """Get the image embedding from a given image path."""
        if self.model is None:
            self.logger.error(
                "CLIP model not available for image embedding."
            )
            return None
        try:
            image: PILImage = Image.open(img_path).convert("RGB")
            image = self._resize_image(image)
            embeddings = self.batch_get_embeddings([image])
            image.close()
            return embeddings[0] if embeddings else None
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

    def batch_get_embeddings(
        self, images: list[PILImage]
    ) -> list[np.ndarray]:
        if self.model is None:
            self.logger.error(
                "CLIP model not available for image embedding."
            )
            return []
        images = [self._resize_image(img) for img in images]
        try:
            inputs = self.processor(
                images=images, return_tensors="pt", padding=True
            ).to(self.device)
            with torch.no_grad():
                image_features = projected_features(
                    self.model.get_image_features(**inputs)
                )
            image_features = image_features / image_features.norm(
                dim=-1, keepdim=True
            )  # Normalize the embeddings
            embedding_array = image_features.cpu().numpy().squeeze()
            if len(images) == 1:
                return [embedding_array]
            return list(embedding_array)
        except Exception as e:
            self.logger.error(
                f"Error processing batch of images with CLIP: {e}",
                exc_info=True,
            )
            # Propagate so the caller skips the batch, as it did when this
            # fell through to an implicit None it then failed to iterate.
            raise

    def get_embedding_from_text(self, text) -> np.ndarray | None:
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
            text_features = projected_features(
                self.model.get_text_features(**inputs)
            )
        text_features = text_features / text_features.norm(
            dim=-1, keepdim=True
        )
        logger.info(
            f"Text embedding computed successfully for: {text}"
        )
        return text_features.cpu().numpy().squeeze()

    def _resize_image(self, image: PILImage) -> PILImage:
        """Resize image to fit within MAX_CLIP_RESOLUTION while maintaining aspect ratio."""
        max_dimension = max(image.size)
        if max_dimension > MAX_CLIP_RESOLUTION:
            image.thumbnail(
                (MAX_CLIP_RESOLUTION, MAX_CLIP_RESOLUTION),
                Image.Resampling.LANCZOS,
            )
        return image
