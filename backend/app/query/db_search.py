import logging

from pydantic import BaseModel
from fastapi import Request
import math

from ..services.institution import InstitutionDirectory
from ..services.metadata import SPECIMEN_TRAIT_COLUMNS, ImageMetaService
from ..services.species_pages import SpeciesPageResolver

logger = logging.getLogger(__name__)


# Searchable by name, but kept out of the free-text sweep.
#
# `coordinate` is numeric and parsed specially. `update_status` and
# `validation_status` are controlled vocabularies -- a query for "valid" would
# otherwise sweep in every VALID coordinate. `county` and `locality` are free
# text over 140,716 and 463,375 values, and each one adds an ILIKE '%q%' scan
# to three queries per request for matches a reader rarely wants when they
# typed a species name. `country` and `state_province` do join the sweep:
# "Brazil" is a search people actually make.
#
# Traits are controlled vocabularies too, and name every image of a species:
# "closed" or "Jun" in the sweep would return a third of the collection.
TARGETED_ONLY_FIELDS = (
    "coordinate",
    "update_status",
    "validation_status",
    "county",
    "locality",
    *SPECIMEN_TRAIT_COLUMNS,
)


class DbSearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]
    specimens: list[dict] = []
    total_specimens: int = 0
    page: int = 1
    limit: int = 50

    @classmethod
    def from_data(
        cls,
        query: str,
        results: list[dict],
        specimens: list[dict] | None = None,
        total_specimens: int = 0,
        page: int = 1,
        limit: int = 50,
    ):
        """ """
        return cls(
            query=query,
            results=results,
            specimens=specimens or [],
            total_specimens=total_specimens,
            page=page,
            limit=limit,
        )

    @classmethod
    def empty(cls, query: str):
        """ """
        return cls(
            query=query, results=[], specimens=[], total_specimens=0, page=1, limit=50
        )


class TextToDbSearch:
    """
    A class to handle text to database search operations on image_meta.
    """

    def __init__(
        self,
        request: Request,
        query: str = "",
        field: str = "all",
        page: int = 1,
        limit: int = 50,
    ):
        """
        Initialize the TextToDbSearch class.
        """
        self.request = request
        self.query = query.strip()
        self.field = field.strip().lower()
        self.page = max(1, page)
        self.limit = limit
        self.offset = (self.page - 1) * self.limit

    def search(self) -> dict | None:
        """
        Perform a text to database search.
        """
        if not self.query:
            logger.warning("Empty query provided for text to database search.")
            return None

        logger.info(
            f"Performing text to database search for query: {self.query} in field: {self.field}"
        )

        meta_service = ImageMetaService(duckdb=self.request.app.state.duck_db)

        valid_fields = [
            "class_dv",
            "family",
            "species",
            "sex",
            "life_stage",
            "source_db",
            "kingdom",
            "phylum",
            "class",
            "order",
            "common_name",
            "coordinate",
            "update_status",
            # Geography. Free-text until `locality`, then controlled codes.
            "country",
            "state_province",
            "county",
            "locality",
            "validation_status",
            # LepTraits, by the species each record resolved to.
            *SPECIMEN_TRAIT_COLUMNS,
        ]

        field = self.field.replace(" ", "_")
        if field not in valid_fields:
            field = "all"

        q_param = f"%{self.query.replace('_', ' ')}%"

        try:
            if field == "coordinate":
                parsed = self.parse_coordinate(self.query)
                if not parsed:
                    logger.info(f"Invalid coordinate format or values: {self.query}")
                    return DbSearchPayload.empty(query=self.query).model_dump()

                lat, lon = parsed
                lat_delta = 50000.0 / 111100.0
                cos_lat = max(math.cos(math.radians(lat)), 0.01)
                lon_delta = lat_delta / cos_lat

                lat_min, lat_max = lat - lat_delta, lat + lat_delta
                lon_min, lon_max = lon - lon_delta, lon + lon_delta

                results_df, specimens_df, total_specimens = (
                    meta_service.search_by_coordinate(
                        lat_min, lat_max, lon_min, lon_max, self.limit, self.offset
                    )
                )
            elif field != "all":
                results_df, specimens_df, total_specimens = (
                    meta_service.search_by_field(
                        field, q_param, self.limit, self.offset
                    )
                )
            else:
                search_fields = [
                    f for f in valid_fields if f not in TARGETED_ONLY_FIELDS
                ]
                results_df, specimens_df, total_specimens = (
                    meta_service.search_all_fields(
                        search_fields, q_param, self.limit, self.offset
                    )
                )

            if results_df.is_empty():
                logger.info(f"No results found for query: {self.query}")
                return DbSearchPayload.empty(query=self.query).model_dump()

            pages = SpeciesPageResolver(self.request.app.state.duck_db)
            db_results = self._process_results(results_df, field, valid_fields, pages)
            db_specimens = self._process_specimens(
                specimens_df, field, valid_fields, pages
            )

            logger.info(
                f"Found {len(db_results)} unique species, total {total_specimens} specimens (showing page {self.page}) for query: {self.query}"
            )
            return DbSearchPayload.from_data(
                query=self.query,
                results=db_results,
                specimens=db_specimens,
                total_specimens=total_specimens,
                page=self.page,
                limit=self.limit,
            ).model_dump()

        except Exception as e:
            logger.error(f"Error performing db search: {e}", exc_info=True)
            raise e

    def _process_results(
        self,
        results_df,
        field: str,
        valid_fields: list[str],
        pages: SpeciesPageResolver,
    ) -> list[dict]:
        """One entry per species page the matching records lead to.

        Each entry names the page it links to. A recorded name that resolves
        to no species with a reachable page is left out: its own page would
        be an orphan. With no harmonization run loaded, the recorded binomial
        stands in, as it always did.
        """
        page_keys = (
            pages.page_keys_for_species(results_df["species"].to_list())
            if pages.available()
            else None
        )
        db_results = []
        seen_species = set()
        for row in results_df.iter_rows(named=True):
            species = row["species"]
            if page_keys is None:
                cleaned_species = self.extract_binomial_species(species)
            else:
                cleaned_species = page_keys.get(species)
                if not cleaned_species:
                    continue

            if cleaned_species in seen_species:
                continue
            seen_species.add(cleaned_species)

            matched_cols = []

            if field != "all":
                if row.get("match_field"):
                    matched_cols.append(field)
            else:
                for col in valid_fields:
                    if row.get(f"match_{col}"):
                        matched_cols.append(col)

            if not matched_cols:
                matched_cols = [field] if field != "all" else ["species"]

            score = self.calculate_score(cleaned_species, matched_cols, self.query)

            db_results.append(
                {
                    "species": cleaned_species,
                    "species_key": cleaned_species,
                    "matched_fields": matched_cols,
                    "score": score,
                }
            )

        db_results.sort(key=lambda x: x["score"], reverse=True)
        return db_results

    def _process_specimens(
        self,
        specimens_df,
        field: str,
        valid_fields: list[str],
        pages: SpeciesPageResolver,
    ) -> list[dict]:
        db_specimens = []
        if specimens_df.is_empty():
            return db_specimens

        # Every specimen is listed, since this is a table of records, but only
        # one whose species has a valid page links to it.
        page_keys = (
            pages.page_keys_for_images(specimens_df["img_id"].to_list())
            if pages.available()
            else None
        )

        search_fields = [f for f in valid_fields if f not in TARGETED_ONLY_FIELDS]
        directory = self._institution_directory(specimens_df)
        for row in specimens_df.iter_rows(named=True):
            matched_cols = []
            if field == "coordinate":
                matched_cols = ["lat", "lon"]
            elif field != "all":
                matched_cols = [field]
            else:
                query_lower = self.query.lower().replace("_", " ")
                for col in search_fields:
                    val = row.get(col)
                    if val is not None and query_lower in str(val).lower().replace(
                        "_", " "
                    ):
                        matched_cols.append(col)
            holder = directory.get(row.get("institution_code") or "", {})
            # We return kingdom, phylum, class, order just in case we need it in the future.
            # The frontend drop this column for viewing.
            #
            # The taxonomy fields come from the colharmonize run and are None
            # until one has been loaded. Only the codes travel per row; their
            # descriptions are served once by GET /taxonomy/codes.
            db_specimens.append(
                {
                    "img_id": row["img_id"],
                    "species": row["species"],
                    "species_key": (
                        page_keys.get(row["img_id"])
                        if page_keys is not None
                        else self.binomial_or_none(row["species"])
                    ),
                    "family": row["family"],
                    "common_name": row["common_name"],
                    "sex": row["sex"],
                    "life_stage": row["life_stage"],
                    "class_dv": row["class_dv"],
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "source_db": row["source_db"],
                    "kingdom": row["kingdom"],
                    "phylum": row["phylum"],
                    "class": row["class"],
                    "order": row["order"],
                    "update_status": row.get("update_status"),
                    "match_method": row.get("match_method"),
                    "display_accepted_name": row.get("display_accepted_name"),
                    "accepted_name": row.get("accepted_name"),
                    "accepted_rank": row.get("accepted_rank"),
                    "accepted_authorship": row.get("accepted_authorship"),
                    "accepted_family": row.get("accepted_family"),
                    "candidate_count": row.get("candidate_count"),
                    # The written locality, joined from gbif_meta. None for the
                    # ~7% of occurrences with no GBIF record, and for every row
                    # until the locality table has been built.
                    "country": row.get("country"),
                    "country_code": row.get("country_code"),
                    "state_province": row.get("state_province"),
                    "county": row.get("county"),
                    "municipality": row.get("municipality"),
                    "locality": row.get("locality"),
                    "verbatim_locality": row.get("verbatim_locality"),
                    # Coordinate validation against GADM. None until
                    # `geoharmonize integrate` has been run. Only the codes travel
                    # per row; their descriptions are served once by
                    # GET /geography/codes.
                    "validation_status": row.get("validation_status"),
                    "coordinate_check": row.get("coordinate_check"),
                    "country_check": row.get("country_check"),
                    "adm1_check": row.get("adm1_check"),
                    "reference_country": row.get("reference_country"),
                    "reference_adm1": row.get("reference_adm1"),
                    # Who holds the specimen and its catalog number, from the
                    # provenance table; the full name and website only when
                    # instharmonize resolved the code. None until those tables
                    # have been built.
                    "institution_code": row.get("institution_code"),
                    "catalog_number": row.get("catalog_number"),
                    "institution_name": holder.get("name"),
                    "institution_homepage": holder.get("homepage"),
                    # LepTraits for the record's accepted species. None until the
                    # trait index is built, and for species LepTraits lacks.
                    **{name: row.get(name) for name in SPECIMEN_TRAIT_COLUMNS},
                    "matched_fields": matched_cols,
                }
            )
        return db_specimens

    def _institution_directory(self, specimens_df) -> dict[str, dict]:
        """The resolved names for the holders on this page, keyed by code.

        One read of the directory for the page rather than one per row. Empty
        when no row carries a code, which also skips the read entirely before
        the provenance table exists.
        """
        if "institution_code" not in specimens_df.columns:
            return {}
        codes = {c for c in specimens_df["institution_code"].to_list() if c}
        if not codes:
            return {}
        directory = InstitutionDirectory(self.request.app.state.duck_db).get_all()
        return {code: directory[code] for code in codes if code in directory}

    @classmethod
    def binomial_or_none(cls, name: str | None) -> str | None:
        """The recorded binomial, or None for a record named only to genus."""
        if not name:
            return None
        key = cls.extract_binomial_species(name)
        return key if "_" in key else None

    @staticmethod
    def extract_binomial_species(name: str) -> str:
        name_clean = name.strip().lower().replace(" ", "_")
        parts = [p for p in name_clean.split("_") if p]
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        return name_clean

    @staticmethod
    def parse_coordinate(query: str) -> tuple[float, float] | None:
        import re

        match = re.search(
            r"^\s*([+-]?\d+(?:\.\d+)?)\s*[\s,;]\s*([+-]?\d+(?:\.\d+)?)\s*$", query
        )
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    return lat, lon
            except ValueError:
                pass
        return None

    @staticmethod
    def calculate_score(species: str, matched_fields: list[str], query: str) -> float:
        query = query.lower()
        species_lower = species.lower().replace("_", " ")

        if query == species_lower or query.replace(" ", "_") == species_lower:
            return 1.0

        if species_lower.startswith(query) or species_lower.replace(
            " ", "_"
        ).startswith(query):
            return 0.95

        if "species" in matched_fields:
            return 0.9

        if "common_name" in matched_fields:
            return 0.85

        taxonomic_fields = {"family", "class", "order", "phylum", "kingdom"}
        if any(f in taxonomic_fields for f in matched_fields):
            return 0.8

        return 0.7
