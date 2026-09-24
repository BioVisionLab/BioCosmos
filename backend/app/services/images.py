import numpy as np
import polars as pl
import logging

from pydantic import BaseModel
from fastapi import Request
from typing import List

from ..services.metadata import ImageMetaService
from ..database.duckdb import DuckDBClient
from ..configs.config import ImageConfig
from ..database.lance import LanceDB
from .unicom import UnicomImageEmbedder
from .clip import ClipEmbedder
from .species_pages import SpeciesPageResolver, attach_page_keys


logger = logging.getLogger(__name__)

# Similarity search is based on LanceDB options:
# https://lancedb.github.io/lancedb/search

# The image table has no scalar index on `img_id`, and LanceDB's memory use
# for an `img_id IN (...)` prefilter grows steeply with the list: 5k IDs peak
# near 5 GB, and a country allowlist (~75k IDs) gets the process OOM-killed.
# Small allowlists are prefiltered in chunks; larger ones rank an unfiltered
# candidate pool (cheap: 50k candidates take under a second) and filter it here.
PREFILTER_CHUNK_SIZE = 200
PREFILTER_MAX_IDS = 2_000
POSTFILTER_POOL_SIZES = (5_000, 50_000)

# Search parameters for the ANN index on the embedding columns.
#
# Twenty probes is LanceDB's own default. The refine factor is the one that
# earns its keep: it pulls ten times the requested rows off the quantized
# index and re-ranks them against the full-precision stored vectors.
#
# Measured on the 619,787-image collection, against exact cosine distance
# computed by hand for the union of both candidate sets: without refinement
# only 70% of the top ten matched the true top ten, and with it 100%. Product
# quantization was not making the search approximate at the margins -- it was
# returning three different images in every ten. That is a wrong answer on a
# panel that makes a claim about the collection, and worth the cost: roughly
# 50ms to 350ms per search, which now runs in a worker thread rather than on
# the event loop.
NPROBES = 20
REFINE_FACTOR = 10


class SpeciesImage(BaseModel):
    """Class to represent species image data."""

    species: str
    imageIds: list[str]

    def to_dict(self) -> dict:
        return {
            "species": self.species,
            "imageIds": self.imageIds,
        }


class ImagePersistData:
    """Class to handle image persistence operations."""

    def __init__(self, lance_db: LanceDB, duckdb: DuckDBClient):
        self.config = ImageConfig()
        self.logger = logging.getLogger(__name__)
        self.db_table = lance_db.create_or_get_collection(self.config.table)
        self.meta_table = duckdb

    def entries(self) -> int | None:
        """Count the number of entries in the image collection."""
        result = LanceDB().count_entries(self.config.table)
        if result is None:
            logger.warning("No entries found in the image collection.")
            return None
        return result

    def get_img_path_by_id(
        self,
        img_id: str,
    ) -> str | None:
        """Fetch the file path for an image by its ID."""
        try:
            results = (
                self.db_table.search()
                .where(f"img_id == '{img_id}'")
                .limit(1)
                .to_polars()
            )
            if results.is_empty():
                self.logger.warning(f"No image found with ID '{img_id}'.")
                return None
            return results["img_path"][0]

        except Exception as e:
            self.logger.error(f"Error fetching image path for ID '{img_id}': {e}")
            return None

    def fetch_image_path(self, species_name: str) -> str | None:
        """Fetch the file path for a species image.

        Looks up image IDs for the species via metadata, then returns
        the disk path for the first image found in LanceDB.
        """
        image_ids = ImageMetaService(duckdb=self.meta_table).get_image_ids_by_species(
            species_name
        )
        if not image_ids:
            return None
        return self.get_img_path_by_id(image_ids[0])

    def fetch_similar_images_from_text(
        self,
        request: Request,
        text: str,
        limit: int = 50,
        max_distance: float | None = None,
        raise_on_error: bool = False,
    ) -> list[dict] | None:
        """Fetch images similar to the given text.
        We use CLIP embeddings for text similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param text: The input text to search for similar images.
        :param limit: The maximum number of similar images to return.
        :param max_distance: Optional maximum cosine distance threshold (0-2, lower is more similar).
                            For color searches, a more lenient threshold (e.g., 1.5) can help.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            text_embedder = ClipEmbedder(
                model=request.app.state.clip_embedder.model,
                processor=request.app.state.clip_embedder.processor,
            )
            query_embedding = text_embedder.get_embedding_from_text(text)
            if query_embedding is None:
                self.logger.warning("Failed to compute text embedding.")
                return None

            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="clip_embeddings",
                limit=limit,
                max_distance=max_distance,
            )
            if similar_images is None:
                if raise_on_error:
                    raise RuntimeError("Text vector search failed.")
                return None
            if similar_images.is_empty():
                self.logger.warning("No similar images found for the given text.")
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the text '{text}'."
            )
            merged_results = self._merge_result_with_metadata(similar_images)
            if merged_results is None:
                return None
            similar_images = self._filter_by_species(merged_results)

            return similar_images.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            if raise_on_error:
                raise
            return None

    def fetch_similar_images_from_text_filtered(
        self,
        request: Request,
        text: str,
        limit: int,
        filter_img_ids: List[str],
        *,
        raise_on_error: bool = False,
    ) -> List[dict]:
        """
        CLIP text search restricted to a specific set of image IDs.

        Mirrors fetch_similar_images_from_text but pre-filters the vector search
        to only images belonging to allowlisted species (from location/trait filters).

        Args:
            request: FastAPI request with CLIP model in app state
            text: Natural language color/pattern description
            limit: Maximum number of results to return
            filter_img_ids: Image IDs to restrict search to (from allowlist species)

        Returns:
            List of dicts with keys [imgId, species, distance] or [] on failure
        """
        if not filter_img_ids:
            logger.warning(
                "fetch_similar_images_from_text_filtered called with empty filter_img_ids"
            )
            return []

        try:
            # Step 1: Compute CLIP text embedding
            text_embedder = ClipEmbedder(
                model=request.app.state.clip_embedder.model,
                processor=request.app.state.clip_embedder.processor,
            )
            query_embedding = text_embedder.get_embedding_from_text(text)
            if query_embedding is None:
                self.logger.warning("Failed to compute text embedding.")
                return []

            cleaned = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="clip_embeddings",
                limit=limit,
                filter_img_ids=filter_img_ids,
            )
            if cleaned is None:
                if raise_on_error:
                    raise RuntimeError("Filtered text vector search failed.")
                return []
            if cleaned.is_empty():
                self.logger.warning(
                    f"No similar images found for text '{text}' within {len(filter_img_ids)} filtered IDs."
                )
                return []

            # Step 5: Merge with metadata (adds species column)
            merged = self._merge_result_with_metadata(cleaned)
            if merged is None or merged.is_empty():
                return []

            # Step 6: Deduplicate by species, keep best (lowest) distance
            filtered = self._filter_by_species(merged)

            self.logger.info(
                f"Filtered color search: '{text}' ? {len(filtered)} species "
                f"within {len(filter_img_ids)} allowlisted images"
            )

            return filtered.to_dicts()

        except Exception as e:
            self.logger.error(
                f"Error in fetch_similar_images_from_text_filtered: {e}",
                exc_info=True,
            )
            if raise_on_error:
                raise
            return []

    def fetch_similar_images_from_bytes(
        self, request: Request, image_bytes: bytes, limit: int = 20
    ) -> list[dict] | None:
        """Fetch images similar to the given image bytes.
        We use UNICOM embeddings for image similarity search.
        We then filter the results to ensure it contains only one image per species.

        :param image_bytes: The input image bytes to search for similar images.
        :param limit: The maximum number of similar images to return.
        :return: A list of dictionaries containing similar image details or None if no matches found.
        """
        try:
            unicom_embedder = UnicomImageEmbedder(
                model=request.app.state.unicom_embedder.model,
                transform=request.app.state.unicom_embedder.transform,
            )
            query_embedding = unicom_embedder.get_embedding_from_bytes(image_bytes)
            if query_embedding is None:
                self.logger.warning("Failed to compute image embedding.")
                return None
            similar_images = self._query_embedding(
                query_vector=query_embedding,
                vector_column_name="unicom_embeddings",
                limit=limit,
            )
            if similar_images is None or similar_images.is_empty():
                self.logger.warning("No similar images found for the given image.")
                return None
            self.logger.info(
                f"Found {len(similar_images)} similar images for the provided image."
            )
            merged_results = self._merge_result_with_metadata(similar_images)
            if merged_results is None:
                return None
            filtered_imgs = self._filter_by_species(merged_results)
            return filtered_imgs.to_dicts()

        except Exception as e:
            self.logger.error(f"Error fetching similar images: {e}")
            return None

    def find_similar_images(
        self,
        image_ids: list[str],
        limit: int = 20,
        filter_img_ids: list[str] | None = None,
        *,
        exclude_species: str | list[str] | None = None,
        min_species: int = 0,
        raise_on_error: bool = False,
    ) -> pl.DataFrame | None:
        """Find images from other species similar to the given image list using UNICOM embeddings.

        Process:
          1. Fetch the UNICOM embeddings of the reference images in bulk.
          2. Average them into a centroid.
          3. Run cosine similarity search against all stored unicom_embeddings.
          4. Drop `exclude_species` and keep one image per species (nearest).
          5. Widen the candidate pool until `min_species` species remain.

        Args:
            image_ids: Reference image IDs used to build the centroid.
            limit: Initial number of candidate images to rank.
            filter_img_ids: Optional candidate image IDs used as a vector-search
                prefilter.
            exclude_species: Species (usually the reference) to leave out.
            min_species: Distinct species wanted after the exclusion.

        Returns:
            DataFrame with imgId, species, distance (smaller = more similar),
            or None if no similar images were found.
        """
        try:
            embeddings = self._query_unicom_embeddings(image_ids)
            if embeddings is None:
                return None
            # Perform similarity search based on the centroid
            centroid: np.ndarray = np.mean(embeddings, axis=0)
            excluded = (
                [exclude_species]
                if isinstance(exclude_species, str)
                else (exclude_species or [])
            )

            # A well-photographed reference species can fill the whole first
            # pool with its own images (the nearest 500 to the monarch
            # centroid are all monarchs), leaving nothing once it is removed.
            pool_sizes = [limit, *(p for p in POSTFILTER_POOL_SIZES if p > limit)]
            similar_images = None
            for pool_size in pool_sizes:
                results = self._query_embedding(
                    query_vector=centroid,
                    vector_column_name="unicom_embeddings",
                    limit=pool_size,
                    filter_img_ids=filter_img_ids,
                )
                if results is None:
                    if raise_on_error:
                        raise RuntimeError("Image vector search failed.")
                    return None
                if results.is_empty():
                    break
                merged_results = self._merge_result_with_metadata(results)
                if excluded and "species" in merged_results.columns:
                    # A subspecies of the reference is the same species.
                    key = self._species_key_expr(pl.col("species"))
                    for species in excluded:
                        excluded_key = self._species_key(species)
                        merged_results = merged_results.filter(
                            (key != excluded_key)
                            & ~key.str.starts_with(f"{excluded_key} ")
                        )
                similar_images = self._filter_by_species(merged_results)
                if similar_images.height >= min_species or results.height < pool_size:
                    break

            if similar_images is None or similar_images.is_empty():
                self.logger.warning(
                    "No other species found near %d reference image IDs.",
                    len(image_ids),
                )
                return None
            self.logger.info(
                "Found %d similar species for %d reference image IDs.",
                similar_images.height,
                len(image_ids),
            )
            return similar_images
        except Exception as e:
            self.logger.error(
                f"Error fetching similar images for image IDs '{image_ids}': {e}"
            )
            if raise_on_error:
                raise
            return None

    @staticmethod
    def _species_key(species: str) -> str:
        return " ".join(species.strip().lower().replace("_", " ").split())

    @staticmethod
    def _species_key_expr(expr: pl.Expr) -> pl.Expr:
        return (
            expr.cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .str.replace_all("_", " ", literal=True)
        )

    def fetch_thumbnail_path(self, species_name: str) -> str | None:
        """Fetch the file path for a species image (for thumbnail generation)."""
        return self.fetch_image_path(species_name)

    def _query_embedding(
        self,
        query_vector: np.ndarray,
        vector_column_name: str,
        limit: int = 5,
        max_distance: float | None = None,
        filter_img_ids: list[str] | None = None,
    ) -> pl.DataFrame | None:
        """Query the database for similar images based on the embedding vector.

        Args:
            query_vector: The embedding vector to search for
            vector_column_name: Name of the vector column to search
            limit: Maximum number of results to return
            max_distance: Optional maximum cosine distance threshold (0-2, lower is more similar).
                         If None, no distance filtering is applied.
            filter_img_ids: Optional image IDs to constrain the vector ranking to.
        """
        try:
            if filter_img_ids is None:
                cleaned_results = self._vector_search(
                    query_vector, vector_column_name, limit
                )
            else:
                allowed_ids = list(dict.fromkeys(str(i) for i in filter_img_ids))
                if not allowed_ids:
                    return pl.DataFrame(
                        schema={"imgId": pl.String, "distance": pl.Float64}
                    )
                if len(allowed_ids) <= PREFILTER_MAX_IDS:
                    cleaned_results = self._prefiltered_vector_search(
                        query_vector, vector_column_name, limit, allowed_ids
                    )
                else:
                    cleaned_results = self._postfiltered_vector_search(
                        query_vector, vector_column_name, limit, allowed_ids
                    )
            if cleaned_results is None:
                return None

            # Apply distance threshold if specified
            # For cosine distance: 0 = identical, 1 = orthogonal, 2 = opposite
            # Lower distance = more similar
            if max_distance is not None and "distance" in cleaned_results.columns:
                before_count = len(cleaned_results)
                cleaned_results = cleaned_results.filter(
                    pl.col("distance") <= max_distance
                )
                self.logger.info(
                    f"Distance filter ({max_distance}): {before_count} -> {len(cleaned_results)} results"
                )

            # We filter image by unique image IDs to avoid duplicates
            cleaned_results = cleaned_results.unique(subset=["imgId"])
            return cleaned_results
        except Exception as e:
            self.logger.error(f"Error querying embeddings: {e}")
            return None

    def _vector_search(
        self,
        query_vector: np.ndarray,
        vector_column_name: str,
        limit: int,
        where: str | None = None,
    ) -> pl.DataFrame | None:
        """Run one cosine search and return only `imgId` and `distance`.

        Projecting to `img_id` keeps LanceDB from materializing the stored
        image bytes and both embedding columns for every candidate.
        """
        search = (
            self.db_table.search(
                query_vector,
                vector_column_name=vector_column_name,
            )
            .distance_type("cosine")
            .select(["img_id"])
            # Both are no-ops on an unindexed column and only take effect once
            # the IVF-PQ index exists. `nprobes` buys recall back from
            # partitioning; `refine_factor` re-ranks the shortlist against the
            # full-precision vectors, which is what keeps product quantization
            # from changing *which* species come back rather than just how
            # fast they arrive. That distinction matters here: this endpoint
            # makes a claim about the collection, not a suggestion.
            .nprobes(NPROBES)
            .refine_factor(REFINE_FACTOR)
        )
        if where is not None:
            search = search.where(where, prefilter=True)
        results = search.limit(limit).to_polars()
        if not {"img_id", "_distance"}.issubset(results.columns):
            return None
        return results.select(
            pl.col("img_id").alias("imgId"),
            pl.col("_distance").alias("distance"),
        )

    def _prefiltered_vector_search(
        self,
        query_vector: np.ndarray,
        vector_column_name: str,
        limit: int,
        allowed_ids: list[str],
    ) -> pl.DataFrame | None:
        """Rank within a small allowlist, one bounded `IN` chunk at a time."""
        frames: list[pl.DataFrame] = []
        for start in range(0, len(allowed_ids), PREFILTER_CHUNK_SIZE):
            chunk = allowed_ids[start : start + PREFILTER_CHUNK_SIZE]
            frame = self._vector_search(
                query_vector,
                vector_column_name,
                limit,
                where=f"img_id IN ({self._quote_ids(chunk)})",
            )
            if frame is None:
                return None
            frames.append(frame)
        return pl.concat(frames).sort("distance").head(limit)

    def _postfiltered_vector_search(
        self,
        query_vector: np.ndarray,
        vector_column_name: str,
        limit: int,
        allowed_ids: list[str],
    ) -> pl.DataFrame | None:
        """Rank an unfiltered candidate pool and keep the allowlisted images.

        The pool grows until it yields `limit` matches or runs out of stages.
        Whatever it returns are still the nearest allowlisted images within the
        pool, so a short result only trims the tail of the ranking.
        """
        matched = pl.DataFrame(schema={"imgId": pl.String, "distance": pl.Float64})
        for pool_size in POSTFILTER_POOL_SIZES:
            pool_limit = max(pool_size, limit)
            candidates = self._vector_search(
                query_vector, vector_column_name, pool_limit
            )
            if candidates is None:
                return None
            matched = candidates.filter(pl.col("imgId").is_in(allowed_ids))
            if matched.height >= limit or candidates.height < pool_limit:
                break
        return matched.sort("distance").head(limit)

    @staticmethod
    def _quote_ids(image_ids: list[str]) -> str:
        return ", ".join(
            f"'{str(img_id).replace(chr(39), chr(39) * 2)}'" for img_id in image_ids
        )

    def _query_unicom_embeddings(self, image_ids: list[str]) -> np.ndarray | None:
        """Fetch the UNICOM embeddings for the given image IDs in bulk.

        One projected read replaces a full-record lookup per image, which
        cost ~0.2 s each (~20 s for a 100-image reference species).
        """
        unique_ids = list(dict.fromkeys(str(i) for i in image_ids if i))
        frames: list[pl.DataFrame] = []
        for start in range(0, len(unique_ids), PREFILTER_CHUNK_SIZE):
            chunk = unique_ids[start : start + PREFILTER_CHUNK_SIZE]
            frames.append(
                self.db_table.search()
                .where(f"img_id IN ({self._quote_ids(chunk)})")
                .select(["img_id", "unicom_embeddings"])
                .limit(len(chunk))
                .to_polars()
            )
        records = pl.concat(frames) if frames else pl.DataFrame()
        if records.is_empty() or "unicom_embeddings" not in records.columns:
            self.logger.warning("No images found for the provided image IDs.")
            return None
        return np.stack(
            [np.asarray(v, dtype=np.float32) for v in records["unicom_embeddings"]]
        )

    def _merge_result_with_metadata(
        self,
        results: pl.DataFrame,
    ) -> pl.DataFrame | None:
        """
        Query the DuckDB for metadata and merge with the results.
        :param results: The polars DataFrame containing search results.
        """
        try:
            if results is None:
                self.logger.warning("No results to merge with metadata.")
                return results

            meta_service = ImageMetaService(duckdb=self.meta_table)
            merged_results = meta_service.merge_meta_with_image_data(results)

            return merged_results

        except Exception as e:
            self.logger.error(f"Error merging results with metadata: {e}")
            return results

    def _filter_by_species(self, results: pl.DataFrame) -> pl.DataFrame:
        """Keep the nearest image of each species page, and only those.

        Each row gains a `speciesKey`: the page it links to. An image whose
        record did not resolve to a species with a reachable page is dropped,
        since its own recorded name would open an orphaned page. Two spellings
        of one species share a page and so make one result.
        """
        try:
            if results is None:
                self.logger.warning("No results to filter by species.")
                return results

            keyed = attach_page_keys(results, SpeciesPageResolver(self.meta_table))
            # Keep the first occurrence of each species (most similar).
            # `keep="first"` is load-bearing: polars defaults to "any", which
            # would discard the sort above and pick an arbitrary image.
            filtered_results = (
                keyed.with_columns(
                    pl.coalesce(
                        pl.col("speciesKey"), pl.col("species").cast(pl.String)
                    ).alias("_dedupe")
                )
                .sort("distance", descending=False)
                .unique(subset=["_dedupe"], keep="first", maintain_order=True)
                .drop("_dedupe")
            )

            return filtered_results

        except Exception as e:
            self.logger.error(f"Error filtering results by species: {e}")
            return results
