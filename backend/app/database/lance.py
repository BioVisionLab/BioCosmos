import logging
import math
import time
from typing import Literal

import lancedb
from lancedb import DBConnection
from lancedb.index import BTree, IvfPq

from ..configs.config import get_lance_db_path
from .model import LanceSchema

logger = logging.getLogger(__name__)

# Below this many rows a brute-force scan is already fast and there is not
# enough data to train IVF partitions against, so an index would be both
# unnecessary and badly fitted.
MIN_ROWS_FOR_INDEX = 5_000

# IVF partitions, as the square root of the row count -- the usual starting
# point, and it keeps the number of vectors scanned per probe roughly constant
# as the collection grows. Capped so a very large collection does not end up
# with so many partitions that probing them dominates the search. No floor is
# needed: MIN_ROWS_FOR_INDEX already puts the smallest indexed collection at
# seventy partitions.
MAX_PARTITIONS = 4_096

# Product quantization splits each vector into this many sub-vectors. Eight
# dimensions per sub-vector is the size the SIMD paths are written for; both
# embedding widths in use (CLIP 512, UNICOM 768) divide evenly by it.
DIMS_PER_SUB_VECTOR = 8

# Columns from the collection's original layout, which stored every image's
# bytes in the table. Images are served from disk now and nothing reads these.
LEGACY_COLUMNS = ("img_bytes", "file_format", "original_size")


class LanceDB:
    """LanceDB wrapper for CLIP model storage."""

    def __init__(self):
        self.db_path = get_lance_db_path()
        self.db = lancedb.connect(self.db_path)
        logger.info(f"LanceDB connected at {self.db_path}")

    def get_db(self) -> DBConnection:
        """Get the LanceDB connection."""
        return self.db

    def count_entries(self, collection_name: str) -> int | None:
        """Count the number of entries in a collection."""
        try:
            row_count = self.db.open_table(collection_name).count_rows()
            logger.info(
                f"Counted {row_count} entries in collection '{collection_name}'."
            )
            return row_count
        except Exception as e:
            logger.error(f"Error counting entries in collection {collection_name}: {e}")
            return None

    def create_or_get_collection(self, collection_name: str):
        """Open the image collection, creating it empty if it does not exist.

        Opens first: this runs on every request that touches the collection,
        and the collection almost always exists.
        """
        try:
            return self.db.open_table(collection_name)
        except ValueError:
            collection = self.db.create_table(
                collection_name, schema=LanceSchema, exist_ok=True
            )
            logger.info(f"Created image collection: {collection_name}")
            return collection

    def schema_problems(self, collection_name: str) -> list[str]:
        """Describe how a collection's columns differ from `LanceSchema`.

        Collections built before images moved to disk carry the image bytes
        and lack `img_path`. They still serve similarity search, but the
        species-image lookup and new ingests do not work against them.
        `scripts/migrate_lance.py` brings them up to date.
        """
        try:
            names = set(self.db.open_table(collection_name).schema.names)
        except ValueError:
            return []
        expected = set(LanceSchema.to_arrow_schema().names)
        problems = [f"missing column '{c}'" for c in sorted(expected - names)]
        problems += [f"legacy column '{c}'" for c in LEGACY_COLUMNS if c in names]
        return problems

    def ensure_scalar_index(self, collection_name: str, column: str) -> bool:
        """Build a BTREE index on a scalar column if it does not have one.

        `img_id` is looked up by equality and `IN` lists on every image
        request; without an index each lookup scans the column. The build
        takes seconds, so unlike the vector index it is safe to run anywhere.

        Failure is logged rather than raised. Returns True when an index was
        built by this call.
        """
        try:
            table = self.db[collection_name]
            existing = {
                c
                for index in table.list_indices()
                for c in (getattr(index, "columns", None) or [])
            }
            if column in existing:
                return False
            table.create_index(column, config=BTree())
            logger.info("Built a scalar index on %s.%s.", collection_name, column)
            return True
        except Exception:
            logger.exception(
                "Could not build a scalar index on %s.%s.", collection_name, column
            )
            return False

    def ensure_vector_index(
        self,
        collection_name: str,
        vector_column: str,
        *,
        metric: Literal["l2", "cosine", "dot"] = "cosine",
    ) -> bool:
        """Build an ANN index on a vector column if it does not have one.

        The production collection already carries one, built out of band -- but
        nothing in this codebase built it, so a rebuilt table or a fresh
        deployment would have come up without one and silently fallen back to a
        brute-force cosine scan over every row. On six hundred thousand
        vectors that is the difference between a search taking fifty
        milliseconds and taking seconds, several times per similarity request.
        This closes that gap: the index becomes a property of the code rather
        than of one machine's data directory.

        Idempotent, and deliberately so: training the index is minutes of work
        and only needs redoing when the vectors themselves change. Restarting
        the service is not that, which is why this is not in the same bucket as
        the full-text reindex.

        Failure is logged rather than raised. An unindexed column is slow, not
        broken, and it is not worth refusing to start over.

        Returns True when an index was built by this call.
        """
        try:
            table = self.db[collection_name]
        except (KeyError, ValueError, FileNotFoundError):
            logger.warning(
                "No '%s' collection, so no vector index to build.",
                collection_name,
            )
            return False

        try:
            existing = {
                column
                for index in table.list_indices()
                for column in (getattr(index, "columns", None) or [])
            }
            if vector_column in existing:
                logger.info(
                    "Vector index already present on %s.%s.",
                    collection_name,
                    vector_column,
                )
                return False

            rows = table.count_rows()
            if rows < MIN_ROWS_FOR_INDEX:
                logger.info(
                    "Only %d rows in %s; brute-force search is fine below %d, "
                    "so no vector index was built.",
                    rows,
                    collection_name,
                    MIN_ROWS_FOR_INDEX,
                )
                return False

            dims = self._vector_dims(table, vector_column)
            if dims is None:
                logger.warning(
                    "Could not read the width of %s.%s, so no vector index was built.",
                    collection_name,
                    vector_column,
                )
                return False

            num_partitions = min(MAX_PARTITIONS, int(math.sqrt(rows)))
            num_sub_vectors = max(1, dims // DIMS_PER_SUB_VECTOR)

            logger.info(
                "Building a %s vector index on %s.%s (%d rows, %d dims, "
                "%d partitions, %d sub-vectors). This runs once and can take "
                "several minutes.",
                metric,
                collection_name,
                vector_column,
                rows,
                dims,
                num_partitions,
                num_sub_vectors,
            )
            started = time.monotonic()
            table.create_index(
                vector_column,
                config=IvfPq(
                    distance_type=metric,
                    num_partitions=num_partitions,
                    num_sub_vectors=num_sub_vectors,
                ),
            )
            logger.info(
                "Vector index on %s.%s built in %.1fs.",
                collection_name,
                vector_column,
                time.monotonic() - started,
            )
            return True
        except Exception:
            logger.exception(
                "Could not build a vector index on %s.%s; searches will fall "
                "back to a full scan.",
                collection_name,
                vector_column,
            )
            return False

    @staticmethod
    def _vector_dims(table, vector_column: str) -> int | None:
        """The width of a fixed-size-list vector column, from the schema."""
        try:
            field = table.schema.field(vector_column)
        except KeyError:
            return None
        return getattr(field.type, "list_size", None)

    def delete_collection(self, collection_name: str):
        """Delete the CLIP collection from the LanceDB."""
        try:
            self.db.drop_table(collection_name)
            logger.info(f"Deleted CLIP collection: {collection_name}")
        except ValueError:
            logger.warning(f"CLIP collection {collection_name} does not exist.")
