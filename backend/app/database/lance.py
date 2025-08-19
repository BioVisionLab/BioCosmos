from calendar import c
from ..services import clip
from ..services import unicom
from .model import LanceSchema
from lancedb import DBConnection
import logging
import lancedb
import os


logger = logging.getLogger(__name__)

DB_DIR = "lance_db"
DB_FNAME = "biocosmos.lance"
DB_PATH = os.path.join(DB_DIR, DB_FNAME)


class LanceDB:
    """LanceDB wrapper for CLIP model storage."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db = lancedb.connect(self.db_path)
        logger.info(f"LanceDB connected at {self.db_path}")

    def get_db(self) -> DBConnection:
        """Get the LanceDB connection."""
        return self.db

    def count_entries(self, collection_name: str) -> int | None:
        """Count the number of entries in a collection."""
        try:
            result: DBConnection = self.db[collection_name]
            row_count = result.count_rows()
            logger.info(
                f"Counted {row_count} entries in collection '{collection_name}'."
            )
            return row_count
        except Exception as e:
            logger.error(
                f"Error counting entries in collection {collection_name}: {e}"
            )
            return None

    def create_or_get_collection(self, collection_name: str):
        """Create or get the CLIP collection in the LanceDB."""
        try:
            collection = self.db.create_table(
                collection_name, schema=LanceSchema
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
