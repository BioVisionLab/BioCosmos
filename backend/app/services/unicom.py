import logging
import torch
import unicom
import base64
import io
from PIL import Image

logger = logging.getLogger(__name__)


UNICOM_COLLECTION_NAME = "biocosmos_images_unicom" # New collection for UNICOM
UNICOM_MODEL_NAME = "ViT-L/14@336px" # UNICOM model
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Load UNICOM Model and Transform (for image search) ---
logger.info(f"Loading UNICOM model: {UNICOM_MODEL_NAME} for image processing...")
try:
    # Load UNICOM model (likely defaults to CPU) and transform
    _model, unicom_transform = unicom.load(UNICOM_MODEL_NAME) # Load without specifying device initially
    # Explicitly move the entire model to the target device
    unicom_model = _model.to(DEVICE)
    unicom_model.eval() # Set model to evaluation mode
    logger.info(f"UNICOM model and transform loaded and moved to {DEVICE} successfully")
except Exception as e:
    logger.error(f"Error loading or moving UNICOM model: {e}", exc_info=True)
    unicom_model = None # Indicate failure

class UnicomImageEmbedder:
    def __init__(self):
        self.model = unicom_model
        self.transform = unicom_transform
        self.device = DEVICE
        self.logger = logger
       

    def get_embedding(self, base64_str):
        if self.model is None:
            self.logger.error("UNICOM model not available for image embedding.")
            return None
        try:
            # Decode base64
            if ',' in base64_str:
                _, encoded = base64_str.split(',', 1)
            else:
                encoded = base64_str
            image_data = base64.b64decode(encoded)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")

            # Apply transform and add batch dimension
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)

            # Get embedding
            with torch.no_grad():
                image_features = self.model(image_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)

            return image_features.cpu().numpy().tolist()
        except Exception as e:
            self.logger.error(f"Could not process base64 image with UNICOM: {e}", exc_info=True)
            return None