import logging
from fastapi import FastAPI
from .routers import image_search, text_search

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(image_search.router)
app.include_router(text_search.router)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the CLIP Service"}
