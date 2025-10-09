import logging
from contextlib import asynccontextmanager
from pydantic import ValidationError

from .database.duckdb import DuckDBClient
from pydantic_settings import BaseSettings

from .services.unicom import UnicomModel
from .database.lance import LanceDB
from .services.clip import ClipModel
from .services.images import ImageEmbedder

from .services.gbif import GbifPersistData
from .services.leptraits import LepTraits

# from .database.duckdb import init_duckdb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import (
    image_search,
    text_search,
    taxon_search,
    taxon_fetch,
    text_summarization,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class AppSettings(BaseSettings):
    """
    Manages application settings and environment variables using Pydantic.
    This centralizes configuration and provides validation.
    """

    DUCK_DIR: str
    LANCE_DIR: str
    IMAGE_DIR: str
    GBIF_DIR: str
    # UF_AI_URL: str
    # UF_AI_API_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_app_settings() -> AppSettings:
    """
    Loads and validates application settings.
    Raises an EnvironmentError if required settings are missing.
    """
    try:
        return AppSettings()
    except ValidationError as e:
        missing_vars = [
            err["loc"][0] for err in e.errors() if "loc" in err
        ]
        error_message = f"Missing or invalid required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        raise EnvironmentError(error_message) from e


def initialize_models(app: FastAPI):
    """Initializes and attaches machine learning models to the app state."""
    logger.info("Initializing CLIP model...")
    clip_model, clip_processor = ClipModel.load_model()
    app.state.clip_embedder = ClipModel(
        model=clip_model, processor=clip_processor
    )
    logger.info("CLIP model initialized successfully.")

    logger.info("Initializing UNICOM model...")
    unicom_model, unicom_transform = UnicomModel.load_model()
    app.state.unicom_embedder = UnicomModel(
        model=unicom_model, transform=unicom_transform
    )
    logger.info("UNICOM model initialized successfully.")


def initialize_lance(app: FastAPI):
    """Initializes and attaches the database to the app state."""
    logger.info("Initializing LanceDB...")
    app.state.lance_db = LanceDB()
    logger.info("LanceDB initialized successfully.")


def initialize_duckdb(app: FastAPI):
    """Initializes and attaches the DuckDB to the app state."""
    logger.info("Initializing DuckDB...")
    app.state.duck_db = DuckDBClient()
    logger.info("DuckDB initialized successfully.")


def run_data_ingestion(app: FastAPI):
    """Runs all necessary data ingestion processes."""
    logger.info("Starting data ingestion processes...")
    LepTraits(app.state.duck_db).ingest()
    logger.info("LepTraits data ingested.")
    GbifPersistData(app.state.duck_db).ingest()
    logger.info("GBIF data ingested.")

    image_embedder = ImageEmbedder(
        clip_model=app.state.clip_embedder.model,
        clip_processor=app.state.clip_embedder.processor,
        unicom_model=app.state.unicom_embedder.model,
        unicom_transform=app.state.unicom_embedder.transform,
        lance_db=app.state.lance_db,
    )
    image_embedder.ingest()
    logger.info("Image embeddings ingested.")
    logger.info(
        "All data ingestion processes completed successfully."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """

    Application lifespan manager.

    This context manager handles the startup and shutdown logic for the FastAPI
    application. On startup, it initializes all necessary services like
    configuration, models, databases, and performs initial data ingestion.
    On shutdown, it will handle cleanup.
    """
    logger.info("Application starting up...")

    try:
        settings = get_app_settings()
        app.state.settings = settings
        logger.info("Application settings loaded and validated.")

        initialize_models(app)
        initialize_lance(app)
        initialize_duckdb(app)
        run_data_ingestion(app)

        logger.info("Application startup completed successfully.")
        yield

    except (EnvironmentError, Exception) as e:
        logger.critical(
            f"A critical error occurred during application startup: {e}"
        )
        raise

    finally:
        logger.info("Application shutting down...")
        app.state.duck_db.close()
        app.state.lance_db = None
        app.state.clip_embedder = None
        app.state.unicom_embedder = None
        logger.info("Application shutdown completed.")


app = FastAPI(
    lifespan=lifespan, title="BIOCOSMOS API", version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(image_search.router)
app.include_router(text_search.router)
app.include_router(taxon_search.router)
app.include_router(taxon_fetch.router)
app.include_router(text_summarization.router)


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the CLIP Service"}
