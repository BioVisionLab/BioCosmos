from ..services.clip import clip
from ..services import unicom
from .model import LanceSchema
from lancedb import DBConnection
import logging
import lancedb
import os


logger = logging.getLogger(__name__)

DB_DIR = "../db"
DB_FNAME = "biocosmos.lance"


class LanceDB:
    """LanceDB wrapper for CLIP model storage."""

    def __init__(self, db_path: str = os.path.join(DB_DIR, DB_FNAME)):
        self.db_path = db_path
        self.db = lancedb.connect(self.db_path)
        self.clip_embedder = clip.ClipEmbedder()
        self.unicom_embedder = unicom.UnicomImageEmbedder()
        logger.info(f"LanceDB connected at {self.db_path}")

    def get_db(self) -> DBConnection:
        """Get the LanceDB connection."""
        return self.db

    def create_or_get_collection(self, collection_name: str):
        """Create or get the CLIP collection in the LanceDB."""
        try:
            schema = LanceSchema(
                clip_ndims=self.clip_embedder.ndims(),
                unicom_ndims=self.unicom_embedder.ndims(),
            )
            collection = self.db.create_table(
                collection_name, schema=schema
            )
            logger.info(f"Created CLIP collection: {collection_name}")
            return collection
        except ValueError:
            collection = self.db[collection_name]
            logger.info(
                f"Using existing CLIP collection: {collection_name}"
            )
            return collection

    def delete_collection(self, collection_name: str):
        """Delete the CLIP collection from the LanceDB."""
        try:
            self.db.drop_table(collection_name)
            logger.info(f"Deleted CLIP collection: {collection_name}")
        except ValueError:
            logger.warning(
                f"CLIP collection {collection_name} does not exist."
            )

    def close(self):
        """Close the LanceDB connection."""
        if self.db:
            self.db.close()
            logger.info("LanceDB connection closed.")
