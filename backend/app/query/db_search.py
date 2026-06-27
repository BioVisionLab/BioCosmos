import logging
import polars as pl

from pydantic import BaseModel
from fastapi import Request
import math

from ..services.metadata import ImageMetaService
from ..services.gbif import GbifPersistData, SearchGbifData

logger = logging.getLogger(__name__)


class DbSearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]
    specimens: list[dict] = []
    total_specimens: int = 0
    page: int = 1
    limit: int = 50

    @classmethod
    def from_data(cls, query: str, results: list[dict], specimens: list[dict] = None, total_specimens: int = 0, page: int = 1, limit: int = 50):
        """ """
        return cls(query=query, results=results, specimens=specimens or [], total_specimens=total_specimens, page=page, limit=limit)

    @classmethod
    def empty(cls, query: str):
        """ """
        return cls(query=query, results=[], specimens=[], total_specimens=0, page=1, limit=50)


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

        logger.info(f"Performing text to database search for query: {self.query} in field: {self.field}")
        
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
                
                results_df, specimens_df, total_specimens = meta_service.search_by_coordinate(
                    lat_min, lat_max, lon_min, lon_max, self.limit, self.offset
                )
            elif field != "all":
                results_df, specimens_df, total_specimens = meta_service.search_by_field(
                    field, q_param, self.limit, self.offset
                )
            else:
                search_fields = [f for f in valid_fields if f != "coordinate"]
                results_df, specimens_df, total_specimens = meta_service.search_all_fields(
                    search_fields, q_param, self.limit, self.offset
                )
                
            if results_df.is_empty():
                logger.info(f"No results found for query: {self.query}")
                return DbSearchPayload.empty(query=self.query).model_dump()
            
            db_results = self._process_results(results_df, field, valid_fields)
            db_specimens = self._process_specimens(specimens_df, field, valid_fields)

            logger.info(f"Found {len(db_results)} unique species, total {total_specimens} specimens (showing page {self.page}) for query: {self.query}")
            return DbSearchPayload.from_data(
                query=self.query, results=db_results, specimens=db_specimens, total_specimens=total_specimens, page=self.page, limit=self.limit
            ).model_dump()
            
        except Exception as e:
            logger.error(f"Error performing db search: {e}", exc_info=True)
            raise e

    def _process_results(self, results_df, field: str, valid_fields: list[str]) -> list[dict]:
        db_results = []
        seen_species = set()
        for row in results_df.iter_rows(named=True):
            species = row["species"]
            cleaned_species = self.extract_binomial_species(species)
            
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
            
            db_results.append({
                "species": cleaned_species,
                "matched_fields": matched_cols,
                "score": score
            })
        
        db_results.sort(key=lambda x: x["score"], reverse=True)
        return db_results

    def _process_specimens(self, specimens_df, field: str, valid_fields: list[str]) -> list[dict]:
        db_specimens = []
        if specimens_df.is_empty():
            return db_specimens
            
        search_fields = [f for f in valid_fields if f != "coordinate"]
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
                    if val is not None and query_lower in str(val).lower().replace("_", " "):
                        matched_cols.append(col)
            # We return kingdom, phylum, class, order just in case we need it in the future.
            # The frontend drop this column for viewing.
            db_specimens.append({
                "img_id": row["img_id"],
                "species": row["species"],
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
                "matched_fields": matched_cols
            })
        return db_specimens

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
        match = re.search(r"^\s*([+-]?\d+(?:\.\d+)?)\s*[\s,;]\s*([+-]?\d+(?:\.\d+)?)\s*$", query)
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
        
        if species_lower.startswith(query) or species_lower.replace(" ", "_").startswith(query):
            return 0.95
            
        if "species" in matched_fields:
            return 0.9
            
        if "common_name" in matched_fields:
            return 0.85
            
        taxonomic_fields = {"family", "class", "order", "phylum", "kingdom"}
        if any(f in taxonomic_fields for f in matched_fields):
            return 0.8
            
        return 0.7
