import logging
from contextlib import asynccontextmanager

from .services.images import ImagePersistData

from .services.gbif import GbifPersistData
from .services.leptraits import LepTraits

# from .database.duckdb import init_duckdb
from fastapi import FastAPI
from .routers import image_search, text_search, taxon_search
# from .database.chroma import init_chroma, init_db
# from .services.embedder import ImageEmbeddingIngestor
# from .services.embedder import ModelType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize the database."""
    logger.info("Starting up the application...")
    try:
        LepTraits().ingest()
        logger.info("LepTraits data ingested successfully.")
        GbifPersistData().ingest()
        logger.info("GBIF data ingested successfully.")
        ImagePersistData().ingest()
        yield
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e


app = FastAPI(
    lifespan=lifespan, title="BIOCOSMOS API", version="0.1.0"
)

app.include_router(image_search.router)
app.include_router(text_search.router)
app.include_router(taxon_search.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")

    return {"message": "Welcome to the CLIP Service"}
