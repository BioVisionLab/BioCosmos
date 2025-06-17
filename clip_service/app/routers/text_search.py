from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging
from transformers import CLIPModel, CLIPProcessor
import torch

router = APIRouter()

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

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
    def __init__(self, model, processor, device, logger):
        self.model = model
        self.processor = processor
        self.device = device
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


@router.get("/text-search/")
async def search_text(query: str):
    """ Search for images based on a text query using CLIP embeddings.
    """
    query = query.strip()
    if query is None or query == "":
        return JSONResponse(content={"error": "Query parameter is required"}, status_code=400)
    if clip_model is None:
        logger.error("CLIP model not available for text search")
        return JSONResponse(content={"error": "CLIP model not available"}, status_code=503)
    
    text_embedder = ClipTextEmbedder(clip_model, clip_processor, DEVICE, logger)
    text_embedding =text_embedder.get_embedding(query)
    if text_embedding is None:
        return JSONResponse(content={"error": "Failed to compute text embedding"}, status_code=500)
    




