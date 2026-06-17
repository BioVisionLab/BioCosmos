import logging

from pydantic import BaseModel
from fastapi import Request

from ..services.metadata import ImageMetaService
from ..services.gbif import GbifPersistData, SearchGbifData

logger = logging.getLogger(__name__)


class DbSearchPayload(BaseModel):
    """ """

    query: str
    results: list[dict]

    @classmethod
    def from_data(cls, query: str, results: list[dict]):
        """ """
        return cls(query=query, results=results)

    @classmethod
    def empty(cls, query: str):
        """ """
        return cls(query=query, results=[])


class TextToDbSearch:
    """
    A class to handle text to database search operations on image_meta.
    """

    def __init__(
        self,
        request: Request,
        query: str = "",
        field: str = "all",
        limit: int = 50,
    ):
        """
        Initialize the TextToDbSearch class.
        """
        self.request = request
        self.query = query.strip()
        self.field = field.strip().lower()
        self.limit = limit

    def search(self) -> dict | None:
        """
        Perform a text to database search.
        """
        if not self.query:
            logger.warning("Empty query provided for text to database search.")
            return None

        logger.info(f"Performing text to database search for query: {self.query} in field: {self.field}")
        
        meta_service = ImageMetaService(duckdb=self.request.app.state.duck_db)
        table_name = meta_service.table

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

        q_param = f"%{self.query}%"
        
        try:
            if field == "coordinate":
                parsed = self.parse_coordinate(self.query)
                if not parsed:
                    logger.info(f"Invalid coordinate format or values: {self.query}")
                    return DbSearchPayload.empty(query=self.query).model_dump()
                
                lat, lon = parsed
                import math
                lat_delta = 100.0 / 111100.0
                cos_lat = max(math.cos(math.radians(lat)), 0.01)
                lon_delta = lat_delta / cos_lat
                
                lat_min, lat_max = lat - lat_delta, lat + lat_delta
                lon_min, lon_max = lon - lon_delta, lon + lon_delta
                
                query = f"""
                    SELECT
                        LOWER(REPLACE(species, ' ', '_')) AS species_key,
                        FIRST(species) AS species,
                        bool_or(TRUE) AS match_field
                    FROM {table_name}
                    WHERE lat BETWEEN ? AND ?
                      AND lon BETWEEN ? AND ?
                    GROUP BY species_key
                    LIMIT ?
                """
                params = [lat_min, lat_max, lon_min, lon_max, self.limit]
                results_df = self.request.app.state.duck_db.execute_prepared_to_pl(query, params)
            elif field != "all":
                col_name = f'"{field}"'
                
                query = f"""
                    SELECT
                        LOWER(REPLACE(species, ' ', '_')) AS species_key,
                        FIRST(species) AS species,
                        bool_or({col_name} ILIKE ?) AS match_field
                    FROM {table_name}
                    WHERE {col_name} ILIKE ?
                    GROUP BY species_key
                    LIMIT ?
                """
                params = [q_param, q_param, self.limit]
                results_df = self.request.app.state.duck_db.execute_prepared_to_pl(query, params)
            else:
                conditions = []
                selects = []
                params = []
                
                search_fields = [f for f in valid_fields if f != "coordinate"]
                for col in search_fields:
                    col_esc = f'"{col}"'
                    
                    conditions.append(f"{col_esc} ILIKE ?")
                    selects.append(f"bool_or({col_esc} ILIKE ?) AS match_{col}")
                    params.append(q_param)
                
                params.extend([q_param] * len(search_fields))
                params.append(self.limit)
                
                selects_str = ", ".join(selects)
                conditions_str = " OR ".join(conditions)
                
                query = f"""
                    SELECT
                        LOWER(REPLACE(species, ' ', '_')) AS species_key,
                        FIRST(species) AS species,
                        {selects_str}
                    FROM {table_name}
                    WHERE {conditions_str}
                    GROUP BY species_key
                    LIMIT ?
                """
                results_df = self.request.app.state.duck_db.execute_prepared_to_pl(query, params)
                
            if results_df.is_empty():
                logger.info(f"No results found for query: {self.query}")
                return DbSearchPayload.empty(query=self.query).model_dump()
            
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
            
            logger.info(f"Found {len(db_results)} results for query: {self.query}")
            return DbSearchPayload.from_data(
                query=self.query, results=db_results
            ).model_dump()
            
        except Exception as e:
            logger.error(f"Error performing db search: {e}", exc_info=True)
            raise e

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
