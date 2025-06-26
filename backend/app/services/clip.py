
import logging
import torch
from transformers import CLIPModel, CLIPProcessor
from .chroma import CLIP_COLLECTION_NAME
from .chroma import query_collection

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if torch.backends.mps.is_available():
    DEVICE = "mps"
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"

# --- Load CLIP Model and Processor (for text search) ---
logger.info(f"Loading CLIP model: {CLIP_MODEL_NAME} for text processing...")
try:
    clip_model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(DEVICE)
    clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
    logger.info(f"CLIP model loaded successfully on device: {DEVICE}")
except Exception as e:
    logger.error(f"Error loading CLIP model: {e}", exc_info=True)
    clip_model = None # Indicate failure

class ClipTextEmbedder:
    """ Class to handle text embedding using CLIP model.

    Args:
        model (CLIPModel): The CLIP model for text embedding.
        processor (CLIPProcessor): The CLIP processor for text preprocessing.
        device (str): The device to run the model on ('cpu' or 'cuda').
    returns:
        List[float]: The normalized text embedding vector.
    """
    def __init__(self):
        self.model = clip_model
        self.processor = clip_processor
        self.device = DEVICE
        self.logger = logger

    def get_embedding(self, text):
        if self.model is None:
            self.logger.error("CLIP model not available for text embedding.")
            return None
        inputs = self.processor(text=text, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().numpy().tolist()

    def get_collection_name(self):
        """Get the name of the CLIP collection."""
        return CLIP_COLLECTION_NAME
    
    async def query(self, query_embedding, n_results=5):
        """Query the CLIP collection in ChromaDB."""
        return await query_collection(query_embedding, n_results=n_results)