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
            "tax_rank",
            "tax_status",
            "family",
            "species",
            "sex",
            "life_stage",
            "lat",
            "lon",
            "source_db",
            "kingdom",
            "phylum",
            "class",
            "order",
            "common_name",
        ]

        field = self.field.replace(" ", "_")
        if field not in valid_fields:
            field = "all"

        q_param = f"%{self.query}%"
        
        try:
            if field != "all":
                col_name = f'"{field}"'
                col_expr = f"CAST({col_name} AS VARCHAR)" if field in ("lat", "lon") else col_name
                
                query = f"""
                    SELECT
                        species,
                        bool_or({col_expr} ILIKE ?) AS match_field
                    FROM {table_name}
                    WHERE {col_expr} ILIKE ?
                    GROUP BY species
                    LIMIT ?
                """
                params = [q_param, q_param, self.limit]
                results_df = self.request.app.state.duck_db.execute_prepared_to_pl(query, params)
            else:
                conditions = []
                selects = []
                params = []
                
                for col in valid_fields:
                    col_esc = f'"{col}"'
                    col_expr = f"CAST({col_esc} AS VARCHAR)" if col in ("lat", "lon") else col_esc
                    
                    conditions.append(f"{col_expr} ILIKE ?")
                    selects.append(f"bool_or({col_expr} ILIKE ?) AS match_{col}")
                    params.append(q_param)
                
                params.extend([q_param] * len(valid_fields))
                params.append(self.limit)
                
                selects_str = ", ".join(selects)
                conditions_str = " OR ".join(conditions)
                
                query = f"""
                    SELECT
                        species,
                        {selects_str}
                    FROM {table_name}
                    WHERE {conditions_str}
                    GROUP BY species
                    LIMIT ?
                """
                results_df = self.request.app.state.duck_db.execute_prepared_to_pl(query, params)
                
            if results_df.is_empty():
                logger.info(f"No results found for query: {self.query}")
                return DbSearchPayload.empty(query=self.query).model_dump()
            
            db_results = []
            for row in results_df.iter_rows(named=True):
                species = row["species"]
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
                
                score = self.calculate_score(species, matched_cols, self.query)
                cleaned_species = species.strip().lower().replace(" ", "_")
                
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
