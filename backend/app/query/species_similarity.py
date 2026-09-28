import logging
import polars as pl

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..services.images import ImagePersistData
from ..services.metadata import ImageMetaService
from ..services.species_pages import SpeciesPageResolver, recorded_binomial_key
from ..services.taxonomy_update import OccurrenceTaxonomy

logger = logging.getLogger(__name__)

# How many neighbours to pull from the vector index per side.
#
# The index is asked for images, but the panel wants distinct taxa. A
# centroid's nearest neighbours are dominated by the query species' own
# images, and occurrences that never resolved are dropped on top of that, so
# the candidate pool has to be far larger than the row count it feeds.
CANDIDATE_MULTIPLIER = 20
MIN_CANDIDATES = 200


class SimilarSpeciesRow(BaseModel):
    """One card in the visually-similar panel."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    # The name as recorded, for display next to the accepted one.
    species: str
    # The species page the card links to: the accepted species' canonical
    # recorded spelling, not this record's own, which may be a synonym or a
    # misspelling whose page is orphaned. See `species_pages`.
    species_key: str
    distance: float
    # Absent until a colharmonize run has been loaded, and on a precomputed
    # table built before the taxonomy columns existed.
    accepted_name: str | None = None
    accepted_rank: str | None = None
    update_status: str | None = None


# The ranks a card can carry. A match that only reached genus names no
# species a reader could compare against, and its card would link to a
# species page that does not exist.
_COMPARABLE_RANKS = frozenset({"species", "subspecies"})


def is_comparable_taxon(record: dict | None) -> bool:
    """Whether a resolved record names a species this panel can show.

    Two ways it does not: the match stopped at genus rank, or the name it
    resolved to is a single word, which is a genus however the rank column
    labels it. Either way there is no binomial, so there is no species page
    to link to and nothing for a reader to compare against.
    """
    if record is None:
        return False
    rank = (record.get("accepted_rank") or "").strip().lower()
    if rank and rank not in _COMPARABLE_RANKS:
        return False
    name = (record.get("display_accepted_name") or "").strip()
    return len(name.split()) >= 2


def has_binomial_record(candidate: dict) -> bool:
    """The same test against a recorded name, for the un-harmonized fallback.

    `image_meta.species` is stored underscored, so a record identified only to
    genus is a single segment.
    """
    return len([part for part in candidate["species"].split("_") if part]) >= 2


def binomial_record_key(species: str) -> str:
    """The binomial route key of a recorded name, for the un-harmonized
    fallback, where there is no accepted species to find a page for."""
    return pl.select(recorded_binomial_key(pl.lit(species))).item()


def similar_species_row(candidate: dict, record: dict | None, species_key: str) -> dict:
    """Shape one card the way the payload declares it."""
    return {
        "imgId": candidate["imgId"],
        "species": candidate["species"],
        "speciesKey": species_key,
        "distance": candidate["distance"],
        "acceptedName": record["display_accepted_name"] if record else None,
        "acceptedRank": record["accepted_rank"] if record else None,
        "updateStatus": record["update_status"] if record else None,
    }


def resolve_similar_species(
    candidates: list[dict],
    taxonomy: OccurrenceTaxonomy,
    exclude_keys: set[str],
    limit: int,
    pages: SpeciesPageResolver,
) -> list[dict]:
    """Map candidate images onto accepted taxa, nearest first.

    Shared by both paths, so a card means the same thing whether it came from
    the precomputed table or from a live vector search. The stored table is
    keyed on the name each record was filed under, so resolving here is what
    turns three spellings of one taxon into one card — and what keeps a
    subspecies of the query species out of its own panel.

    Order matters: candidates that never resolved are dropped and the taxa are
    de-duplicated before the cut, so a short list means the source was short,
    not that filtering ate the results.
    """
    if not candidates:
        return []

    resolved = taxonomy.get_for_images([row["imgId"] for row in candidates])
    if not resolved:
        # No harmonization run has been loaded. Fall back to the recorded
        # names so the panel still renders, rather than showing nothing.
        logger.info(
            "No taxonomic update available; "
            "falling back to recorded names for similar species."
        )
        return [
            similar_species_row(row, None, binomial_record_key(row["species"]))
            for row in candidates
            if has_binomial_record(row)
        ][:limit]

    page_keys = pages.page_keys_for_images([row["imgId"] for row in candidates])
    rows: list[dict] = []
    seen: set[str] = set()
    seen_pages: set[str] = set()
    for candidate in sorted(candidates, key=lambda row: row["distance"]):
        record = resolved.get(candidate["imgId"])
        if record is None:
            continue
        key = record["accepted_key"]
        # Skip whatever did not resolve to a species: an unidentifiable name,
        # or a match that stopped at genus, is not something a reader can
        # compare against and has no species page to open.
        if not key or key in exclude_keys or key in seen:
            continue
        if not is_comparable_taxon(record):
            continue
        # A species with no page a link can reach would leave the card
        # pointing at an orphan, so it is not shown at all.
        page = page_keys.get(candidate["imgId"])
        if not page or page in seen_pages:
            continue
        seen.add(key)
        seen_pages.add(page)
        rows.append(similar_species_row(candidate, record, page))
        if len(rows) >= limit:
            break
    return rows


class VisuallySimilarSpeciesPayload(BaseModel):
    """
    A class to represent visually similar species data.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    dorsal: list[SimilarSpeciesRow]
    ventral: list[SimilarSpeciesRow]


class SpeciesSimilarity:
    """
    A class to handle species similarity search operations.
    """

    def __init__(self, request: Request, limit: int = 10):
        """
        Initialize the SpeciesSimilarity class.
        Args:
            request (Request): The FastAPI request object.
        """
        self.lance_db = request.app.state.lance_db
        self.duck_db = request.app.state.duck_db
        self.limit = limit
        self.candidate_limit = max(limit * CANDIDATE_MULTIPLIER, MIN_CANDIDATES)
        # One lookup for both sides; it caches its own table probe.
        self.taxonomy = OccurrenceTaxonomy(duckdb_client=self.duck_db)
        self.pages = SpeciesPageResolver(self.duck_db)

    def find_similar_species(
        self, species_name: str, side: str | None = None
    ) -> dict | None:
        """
        Find species similar to the given species name using image similarity.

        Args:
            species_name (str): The species name to find similar species for.
            side (str | None): "dorsal" or "ventral" to search only that side,
                leaving the other list empty. The panel requests the two
                separately so whichever resolves first can paint. The vector
                scan was always per-side; splitting only repeats the image-id
                and taxonomy lookups, which are DuckDB reads.

        Returns:
            dict | None: A dictionary containing similar species data or None if not found.
        """
        # Get image ID for the species
        try:
            image_ids = self._get_image_ids_for_species(species_name)
            if image_ids is None or image_ids.is_empty():
                logger.info(f"No image IDs found for species: {species_name}")
                return None
            # The taxa this species' own records resolve to, so a neighbour
            # that is this same species under another spelling — a subspecies
            # of it, or a synonym — is kept out of its own panel.
            exclude_keys = self.taxonomy.accepted_keys_for_species(species_name)
            dorsal: list[dict] = (
                self._get_similar_images_by_side(
                    species_images=image_ids,
                    species_name=species_name,
                    side="dorsal",
                    exclude_keys=exclude_keys,
                )
                if side in (None, "dorsal")
                else []
            )
            ventral: list[dict] = (
                self._get_similar_images_by_side(
                    species_images=image_ids,
                    species_name=species_name,
                    side="ventral",
                    exclude_keys=exclude_keys,
                )
                if side in (None, "ventral")
                else []
            )
            payload = VisuallySimilarSpeciesPayload.model_validate(
                {"dorsal": dorsal, "ventral": ventral}
            )
            return payload.model_dump(by_alias=True)
        except Exception as e:
            logger.error(
                f"Error retrieving image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return None

    def _get_similar_images(
        self,
        species_name: str,
        image_ids: list[str],
        exclude_keys: set[str],
    ) -> list[dict]:
        try:
            similar_images: pl.DataFrame | None = ImagePersistData(
                lance_db=self.lance_db,
                duckdb=self.duck_db,
            ).find_similar_images(
                image_ids=image_ids,
                limit=self.candidate_limit,
                exclude_species=species_name,
                # Headroom for synonyms and subspecies that resolve away.
                min_species=self.limit * 2,
            )
            if similar_images is None or similar_images.is_empty():
                logger.info("No similar images found.")
                return []
            return self._resolve_accepted(similar_images, species_name, exclude_keys)
        except Exception as e:
            logger.error(
                f"Error retrieving similar images: {e}",
                exc_info=True,
            )
            return []

    def _get_similar_images_by_side(
        self,
        species_images: pl.DataFrame,
        species_name: str,
        side: str,
        exclude_keys: set[str] | None = None,
    ) -> list[dict]:
        try:
            side_images: list[str] | None = self._filter_by_side(
                species_images, side=side
            )
            if side_images is None or len(side_images) == 0:
                logger.info(f"No {side} similar images found.")
                return []
            similar_images = self._get_similar_images(
                species_name=species_name,
                image_ids=side_images,
                exclude_keys=exclude_keys or set(),
            )
            return similar_images
        except Exception as e:
            logger.error(
                f"Error retrieving {side} similar images: {e}",
                exc_info=True,
            )
            return []

    def _resolve_accepted(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
        exclude_keys: set[str],
    ) -> list[dict]:
        """Resolve the vector-search candidates through the taxon lookup.

        The recorded-name self filter runs first and is belt and braces: it
        matters only when the query species did not resolve, so `exclude_keys`
        is empty and cannot speak for it.
        """
        candidates = self._filter_similar_images(similar_images, species_name)
        return resolve_similar_species(
            candidates, self.taxonomy, exclude_keys, self.limit, self.pages
        )

    def _filter_similar_images(
        self,
        similar_images: pl.DataFrame,
        species_name: str,
    ) -> list[dict]:
        """
        Filter out images that belong to the same species as the query species.

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
            species_name (str): The species name to filter out.
        Returns:
            list[dict]: List of similar images not belonging to the query species.
        """
        filtered_images = similar_images.filter(
            pl.col("species").str.to_lowercase().str.replace_all(" ", "_", literal=True)
            != species_name.lower().replace(" ", "_")
        )
        if filtered_images is None or filtered_images.is_empty():
            logger.info(
                f"No similar images found for species different than: {species_name}"
            )
            return []
        return filtered_images.to_dicts()

    def _get_image_ids_for_species(self, species_name: str) -> pl.DataFrame | None:
        """
        Get image IDs for a given species.
        Args:
            species_name (str): The species name to get image IDs for.
        Returns:
            pl.DataFrame | None: DataFrame containing image IDs or None if not found.
        """
        try:
            meta_service = ImageMetaService(duckdb=self.duck_db)
            image_meta: pl.DataFrame | None = meta_service.get_image_meta_by_species(
                species=species_name
            )
            if image_meta is None or image_meta.is_empty():
                logger.info(f"No images found for species: {species_name}")
                return None
            # Need to remove .png extension if present
            return image_meta
        except Exception as e:
            logger.error(
                f"Error fetching image IDs for species {species_name}: {e}",
                exc_info=True,
            )
            return None

    def _filter_by_side(
        self, similar_images: pl.DataFrame, side: str
    ) -> list[str] | None:
        """
        Filter similar images by side (dorsal or ventral).

        Args:
            similar_images (pl.DataFrame): DataFrame containing similar images.
        Returns:
            list[str] | None: List of dorsal image IDs or None if none found.
        """
        filtered_images = similar_images.filter(
            pl.col("class_dv").str.to_lowercase() == side.lower()
        )
        if filtered_images is None or filtered_images.is_empty():
            logger.info(f"No {side} images found in similar images.")
            return None
        return self._get_image_ids(filtered_images)

    def _get_image_ids(self, image_meta: pl.DataFrame) -> list[str]:
        """
        Extract image IDs from image metadata.

        Args:
            image_meta (pl.DataFrame): DataFrame containing image metadata.
        Returns:
            list[str]: List of image IDs.
        """
        return image_meta.select(pl.col("img_id")).to_series().to_list()
