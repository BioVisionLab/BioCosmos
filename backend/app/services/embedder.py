import torch
import logging
import unicom
import chromadb
from PIL import Image
from chromadb.utils.batch_utils import create_batches  # Utility for batching

IMAGE_BASE_DIR = "../public/images/nymphalidae_new" # Relative path from clip_service folder
CHROMA_DB_PATH = "./chroma_db" # Directory to store Chroma data locally
# Use UNICOM specific names
COLLECTION_NAME = "biocosmos_images_unicom"
MODEL_NAME = "ViT-L/14@336px"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32 # UNICOM ViT-L is larger, might need smaller batch size

logger = logging.getLogger(__name__)


class ImageEmbedder:
    def __init__(self, model_name=MODEL_NAME, device=DEVICE):
        self.model_name = model_name
        self.device = device
        self.model, self.transform = self.load_model()

    def load_model(self):
        try:
            logger.info(f"Loading UNICOM model: {self.model_name}...")
            _model, transform = unicom.load(self.model_name)
            model = _model.to(self.device)
            model.eval()
            logger.info(f"UNICOM model and transform loaded and moved to {self.device} successfully")
            return model, transform
        except Exception as e:
            logger.error(f"Fatal error loading or moving UNICOM model: {e}", exc_info=True)
            raise e
