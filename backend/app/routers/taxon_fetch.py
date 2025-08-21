from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/taxon/{species_name}")
async def fetch_taxon_img(species_name: str):
    logger.info(f"Fetching taxon image for species: {species_name}")
    img_bytes = b""
    # Implement the logic to fetch taxon image
    return StreamingResponse(img_bytes, media_type="image/jpeg")
