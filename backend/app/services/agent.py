"""
Agent-based semantic search service for biodiversity data.

This module implements an intelligent search system that uses OpenAI function calling
to route queries to multiple specialized data sources (color, location, traits, image similarity).
Results are aggregated using a weighted ranking formula that prioritizes species matching
multiple criteria and penalizes those found by fewer tools.

Key features:
- Single-turn LLM execution for efficient token usage
- Parallel tool execution for performance
- Dynamic weight normalization when features are missing
- Weighted scoring with tool count penalty
- Cosine distance normalization for color similarity
- Smart image ID selection based on search context
"""

import logging
import json
import asyncio

import polars as pl

from typing import List, Dict, Any

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel
from fastapi import Request
from openai import OpenAI

from .image_meta import ImageMetaService
from ..configs.config import OpenAIConfig
from .images import ImagePersistData
from .gbif import GbifPersistData
from .leptraits import LepTraits


logger = logging.getLogger(__name__)


class AgentSearchResult(BaseModel):
    """
    Represents a single species result from the agent search.

    Attributes:
        img_id: Image identifier - context-aware selection:
                - If color search used: Best matching image ID from color similarity
                - Otherwise: Main/representative image ID for the species
        species: Scientific name of the species (e.g., "Danaus plexippus")
        tool_calls: List of tool names that returned this species
                    (e.g., ["search_by_color", "search_by_location"])
        score: Computed ranking score (higher is better).
               Calculated using weighted formula with tool penalty.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    img_id: str
    species: str
    tool_calls: List[str]
    score: float = 0.0

    @field_serializer("score")
    def serialize_score(self, score: float) -> float:
        """Serialize score to 4 decimal places for cleaner output."""
        return round(score, 4)


class AgentSearchService:
    """
    Agent-based search service using OpenAI function calling for intelligent routing.

    This service orchestrates searches across multiple biodiversity data sources:
    1. Color-based search: Uses CLIP embeddings and cosine distance
    2. Location-based search: Queries GBIF occurrence data
    3. Trait-based search: Filters by habitat preferences (canopy, edge, moisture, disturbance)
    4. Image similarity: Finds visually similar species using vector embeddings

    Ranking Algorithm:
    ------------------
    Species are ranked using a weighted formula with dynamic normalization:

        Final Score = sum of per-tool contributions - penalty

    Where per-tool contributions are:
        - Color:      w_c * (1 - distance / 2)   [distance in [0,2]]
        - Location:   w_l * 1.0                  [binary match]
        - Traits:     w_t * 1.0                  [binary match]
        - Similarity: w_s * (1 - distance)       [distance in [0,1]]

    Weights are dynamically renormalized based on which tools were invoked,
    so scores always remain in [0, 1] before the penalty.

    Penalty:
        penalty = 0.15 * (num_tools_used - num_tools_matched_for_species)

    This ensures species found by multiple tools rank higher than those
    found by only one tool.

    Image ID Selection:
    -------------------
        - If color or similarity search used: Returns image ID with best match
        - Otherwise: Returns main/representative image ID for the species
    """

    # Penalty per missing tool hit
    TOOL_PENALTY = 0.15

    def __init__(self, request: Request):
        """
        Initialize the agent search service with required dependencies.

        Args:
            request: FastAPI request object containing app state with database connections

        Raises:
            ValueError: If OpenAI API credentials are not configured
        """
        config = OpenAIConfig()
        if not config.api_key or not config.api_url:
            raise ValueError(
                "OpenAI API key and URL must be configured for agent search"
            )
        self.client = OpenAI(
            base_url=config.api_url,
            api_key=config.api_key,
        )
        self.model = config.model or "gpt-4o"
        self.request = request

        # Initialize data access services
        self.image_service = ImagePersistData(
            lance_db=request.app.state.lance_db,
            duckdb=request.app.state.duck_db,
        )
        self.image_meta_service = ImageMetaService(
            duckdb=request.app.state.duck_db
        )
        self.gbif_service = GbifPersistData(
            duckdb=request.app.state.duck_db
        )
        self.leptraits_service = LepTraits(
            duckdb=request.app.state.duck_db
        )

        # Base ranking weights - sum to 1.0
        # Dynamically renormalized based on which tools are invoked
        self.weight_color = 0.25
        self.weight_location = 0.25
        self.weight_traits = 0.25
        self.weight_similarity = 0.25  # Separate weight for image similarity

        # Maps tool names to their base weights for dynamic normalization
        self._tool_weights: Dict[str, float] = {
            "color_search": self.weight_color,
            "location_search": self.weight_location,
            "trait_search": self.weight_traits,
            "similarity_search": self.weight_similarity,
        }

    async def search(self, query: str) -> pl.DataFrame:
        """
        Two-phase search pipeline:

        Phase 1 ? Filter: Run location and/or traits tools in parallel.
                        Intersect their species sets to form an allowlist.
                        Results are cached to avoid re-execution.

        Phase 2 ? Rank:   If ranking tools (color, similarity) were requested,
                        run them scoped to allowlist image IDs only.
                        If no ranking tools, use filter tool scores directly.

        Args:
            query: Natural language search query

        Returns:
            pl.DataFrame with columns [imgId, species, score, tool_names]
            sorted by score descending. Returns empty DataFrame if no results.

        Raises:
            Exception: If OpenAI API call fails (logged and re-raised)
        """
        tools = self._get_tools()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a search router. Your ONLY job is to decompose the user's request into parallel tool calls. "
                    "Follow these decomposition rules strictly:\n"
                    "1. VISUALS: If the query contains colors (e.g., 'blue', 'orange'), patterns ('spotted'), or visual descriptions, you MUST call 'search_by_color'.\n"
                    "2. LOCATION: If the query contains a country or region (e.g., 'Brazil', 'Amazon'), you MUST call 'search_by_location'.\n"
                    "3. TRAITS: If the query mentions habitat (e.g., 'canopy', 'dry'), call 'search_by_traits'.\n"
                    "4. COMBINATION: For queries like 'Blue butterfly in Brazil', you MUST call BOTH 'search_by_color' (arg: 'blue') AND 'search_by_location' (arg: 'Brazil').\n"
                    "5. FILTERING: Ignore generic terms like 'butterfly', 'insect', or 'species'. Focus ONLY on the distinguishing attributes.\n"
                    "6. SPECIFIC NAMES: Only use 'search_by_image_similarity' if the user specifically asks for species 'similar to' a scientific name."
                ),
            },
            {"role": "user", "content": query},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                timeout=30.0,
            )

            message = response.choices[0].message
            if not message.tool_calls:
                logger.warning(f"LLM made no tool calls for query: {query}")
                return pl.DataFrame()

            # ?? Parse LLM tool calls ??????????????????????????????????????????????
            parsed_calls: List[Dict[str, Any]] = []
            for tool_call in message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse args for {tool_call.function.name}")
                    continue
                parsed_calls.append({"name": tool_call.function.name, "args": args})

            if not parsed_calls:
                logger.warning("All tool call arguments failed to parse")
                return pl.DataFrame()

            # ?? Dynamic Weight Normalization ??????????????????????????????????????
            tool_name_map = {
                "search_by_color": "color_search",
                "search_by_location": "location_search",
                "search_by_traits": "trait_search",
                "search_by_image_similarity": "similarity_search"
            }
            invoked_tool_names = [c["name"] for c in parsed_calls]
            total_weight = sum(self._tool_weights.get(tool_name_map.get(name, ""), 0.0) for name in invoked_tool_names)
            
            normalized_weights = {}
            for name in invoked_tool_names:
                mapped_name = tool_name_map.get(name)
                if mapped_name and total_weight > 0:
                    normalized_weights[name] = self._tool_weights[mapped_name] / total_weight
                else:
                    normalized_weights[name] = 1.0 # fallback

            FILTER_TOOLS  = {"search_by_location", "search_by_traits"}
            RANKING_TOOLS = {"search_by_color", "search_by_image_similarity"}

            filter_calls  = [c for c in parsed_calls if c["name"] in FILTER_TOOLS]
            ranking_calls = [c for c in parsed_calls if c["name"] in RANKING_TOOLS]

            logger.info(
                f"Filter tools: {[c['name'] for c in filter_calls]} | "
                f"Ranking tools: {[c['name'] for c in ranking_calls]}"
            )

            # ?? Phase 1: Run filter tools in parallel, build allowlist ???????????
            # allowlist_species = None means no filter was applied (ranking-only query)
            allowlist_species: set[str] | None = None
            cached_filter_rows: Dict[str, List[Dict]] = {}

            if filter_calls:
                filter_results = await asyncio.gather(
                    *[self._execute_tool(c["name"], c["args"], normalized_weights.get(c["name"], 0.25)) for c in filter_calls],
                    return_exceptions=True,
                )

                per_tool_species: List[set[str]] = []
                for i, result in enumerate(filter_results):
                    tool_name = filter_calls[i]["name"]
                    if isinstance(result, Exception):
                        logger.error(f"Filter tool '{tool_name}' failed: {result}")
                        continue
                    if not result or (isinstance(result, dict) and "error" in result):
                        logger.warning(f"Filter tool '{tool_name}' returned empty/error")
                        continue

                    cached_filter_rows[tool_name] = result
                    species_set = {row["species"] for row in result}
                    per_tool_species.append(species_set)
                    logger.info(f"Filter tool '{tool_name}' returned {len(species_set)} species")

                if per_tool_species:
                    # Intersect results from all filter tools
                    allowlist_species = per_tool_species[0].intersection(*per_tool_species[1:])
                    logger.info(
                        f"Allowlist after intersection of {len(per_tool_species)} filter tools: "
                        f"{len(allowlist_species)} species"
                    )

                    # Fall back to union if intersection is empty
                    if not allowlist_species:
                        logger.warning(
                            "Filter intersection produced 0 species ? falling back to union"
                        )
                        allowlist_species = set().union(*per_tool_species)
                        logger.info(f"Union fallback allowlist: {len(allowlist_species)} species")

            # ?? Phase 2: Score results ????????????????????????????????????????????
            all_results: List[Dict] = []
            active_tool_names: List[str] = []

            if ranking_calls:
                # Include filter results in final scores if they passed the allowlist
                if allowlist_species is not None:
                    # 1) Add filter rows to all_results to ensure they contribute to the final score
                    for call in filter_calls:
                        rows = cached_filter_rows.get(call["name"], [])
                        filtered_rows = [r for r in rows if r["species"] in allowlist_species]
                        if filtered_rows:
                            active_tool_names.append(call["name"])
                            all_results.extend(filtered_rows)
                    
                    # 2) Fetch ALL image IDs for the allowlisted species. 
                    #    We must not limit to just the single main image ID returned by the filters, 
                    #    otherwise color search cannot find the best visually matching image.
                    allowlist_img_ids = self.image_meta_service.get_image_ids_for_species_list(
                        list(allowlist_species)
                    )
                    
                    if not allowlist_img_ids:
                        logger.warning(
                            "No image IDs found for allowlisted species ? cannot scope ranking tools"
                        )
                        return pl.DataFrame()
                else:
                    allowlist_img_ids = None

                for call in ranking_calls:
                    weight = normalized_weights.get(call["name"], 0.25)
                    if allowlist_img_ids is not None:
                        rows = await self._execute_tool_scoped(
                            call["name"],
                            call["args"],
                            allowlist_img_ids,
                            allowlist_species,
                            weight,
                        )
                    else:
                        # Ranking-only query (no location/traits) ? search full index
                        rows = await self._execute_tool(call["name"], call["args"], weight)

                    if isinstance(rows, Exception):
                        logger.error(f"Ranking tool '{call['name']}' failed: {rows}")
                        continue
                    if not rows or (isinstance(rows, dict) and "error" in rows):
                        logger.warning(f"Ranking tool '{call['name']}' returned empty/error")
                        continue

                    active_tool_names.append(call["name"])
                    all_results.extend(rows)

            else:
                # No ranking tools ? filter tools ARE the scores.
                # Applies to location-only or traits-only queries.
                if allowlist_species is not None:
                    for call in filter_calls:
                        rows = cached_filter_rows.get(call["name"], [])
                        # Only keep species that passed the full intersection/union allowlist
                        filtered_rows = [r for r in rows if r["species"] in allowlist_species]
                        if filtered_rows:
                            active_tool_names.append(call["name"])
                            all_results.extend(filtered_rows)
                else:
                    logger.warning("No filter or ranking tools produced any results")
                    return pl.DataFrame()

            if not all_results:
                logger.warning(f"No results collected for query: {query}")
                return pl.DataFrame()

            logger.info(
                f"Collected {len(all_results)} rows from tools: {set(active_tool_names)} "
                f"for aggregation"
            )

            return self._aggregate_results(all_results, active_tool_names)

        except Exception as e:
            logger.error(f"Error in agent search: {e}", exc_info=True)
            raise

    def _aggregate_results(
        self, results: List[Dict], active_tool_names: List[str]
    ) -> pl.DataFrame:
        if not results:
            return pl.DataFrame()

        df = pl.DataFrame(results)

        expected_cols = {"imgId", "species", "score", "tool_names"}
        missing = expected_cols - set(df.columns)
        if missing:
            logger.error(f"Result rows missing columns: {missing}")
            return pl.DataFrame()

        num_tools_used = len(set(active_tool_names))

        # Group by species: sum scores, collect tools, pick best imgId
        aggregated = (
            df.group_by("species")
            .agg([
                # Prefer imgId from color/similarity rows (best visual match)
                pl.when(
                    pl.col("tool_names").is_in(["search_by_color", "search_by_image_similarity"])
                )
                .then(pl.col("imgId"))
                .otherwise(None)
                .drop_nulls()
                .first()
                .fill_null(pl.col("imgId").first())
                .alias("imgId"),
                pl.col("score").sum().alias("score"),
                pl.col("tool_names").unique().alias("tool_names"),
                pl.col("tool_names").n_unique().alias("tool_hit_count"),
            ])
            .with_columns(
                # Penalty only applies when multiple ranking tools are active
                # (e.g., color + similarity both fired)
                (
                    pl.col("score")
                    - self.TOOL_PENALTY * (num_tools_used - pl.col("tool_hit_count"))
                ).alias("score")
            )
            .drop("tool_hit_count")
            .sort("score", descending=True)
        )

        logger.info(
            f"Aggregated {len(df)} rows ? {len(aggregated)} unique species | "
            f"top score: {aggregated['score'][0]:.4f}"
        )
        return aggregated

    async def _execute_tool_scoped(
        self,
        function_name: str,
        function_args: Dict[str, Any],
        allowlist_img_ids: List[str],
        allowlist_species: set[str],
        weight: float,
    ) -> list[dict]:
        """
        Execute a ranking tool (color or similarity) restricted to a pre-filtered
        set of image IDs. This scopes CLIP/vector search to only images belonging
        to species that passed the location/trait filter.

        Args:
            function_name: "search_by_color" or "search_by_image_similarity"
            function_args: LLM-parsed arguments for the tool
            allowlist_img_ids: Exact Image IDs returned by the locality/traits filtering
            allowlist_species: Set of species names that passed the filter
            weight: Normalized score weight dynamically assigned to this tool

        Returns:
            List of result dicts with keys [imgId, species, score, tool_names]
        """
        if function_name == "search_by_color":
            color_description = function_args.get("color_description", "")
            if not color_description:
                return []

            image_limit = max(function_args.get("limit", 150) * 10, 300)

            # Search only within allowlisted image IDs explicitly returned by locality/traits
            raw_results = self.image_service.fetch_similar_images_from_text_filtered(
                request=self.request,
                text=color_description,
                limit=image_limit,
                filter_img_ids=allowlist_img_ids,
            )

            if not raw_results:
                return []

            results_df = (
                raw_results
                if isinstance(raw_results, pl.DataFrame)
                else pl.DataFrame(raw_results)
            )

            if results_df.is_empty():
                return []

            # Keep only rows whose species are in the allowlist (safety filter)
            results_df = results_df.filter(pl.col("species").is_in(list(allowlist_species)))

            if results_df.is_empty():
                return []

            # Deduplicate by species: keep best (lowest) distance per species
            results_df = results_df.sort("distance").unique(subset=["species"], keep="first")

            return self._build_result_df(
                df=results_df,
                score_expr=pl.lit(weight) * (1 - pl.col("distance") / 2),
                tool_name="search_by_color",
            ).to_dicts()

        elif function_name == "search_by_image_similarity":
            reference_species = (function_args.get("reference_species") or "").strip()
            if not reference_species:
                return []

            image_ids = self.image_meta_service.get_image_ids_by_species(reference_species)
            if not image_ids:
                return []

            # Search similarity but restrict results to allowlisted species
            similar_images: pl.DataFrame = self.image_service.find_similar_images(
                image_ids=image_ids,
                limit=function_args.get("limit", 400),
            )

            if similar_images is None or similar_images.is_empty():
                return []

            # Filter to allowlisted species only
            similar_images = similar_images.filter(
                pl.col("species").is_in(list(allowlist_species))
            )

            if similar_images.is_empty():
                return []

            return self._build_result_df(
                df=similar_images,
                score_expr=pl.lit(weight) * (1 - pl.col("distance")),
                tool_name="search_by_image_similarity",
            ).to_dicts()

        else:
            return {"error": f"_execute_tool_scoped does not support: {function_name}"}

    async def _execute_tool(
        self, function_name: str, function_args: Dict[str, Any], weight: float
    ) -> list[dict]:
        """
        Route a tool call to the appropriate search method and return
        a standardized list of result dicts.

        All results have the shape:
            { "imgId": str, "species": str, "score": float, "tool_names": str }

        Args:
            function_name: One of the tool names defined in _get_tools()
            function_args: Parsed arguments from the LLM tool call
            weight: Normalized score weight dynamically assigned to this tool

        Returns:
            List of result dicts, or {"error": str} on unknown tool
        """
        if function_name == "search_by_image_similarity":
            return await self._search_by_image_similarity(
                reference_species=function_args.get("reference_species"),
                weight=weight,
                limit=function_args.get("limit", 400),
            )
        elif function_name == "search_by_location":
            return await self._search_by_location(
                location=function_args.get("location"),
                weight=weight,
                limit=function_args.get("limit", 400),
            )
        elif function_name == "search_by_color":
            return await self._search_by_color(
                color_description=function_args.get("color_description"),
                weight=weight,
                limit=function_args.get("limit", 50),
            )
        elif function_name == "search_by_traits":
            return await self._search_by_traits(
                canopy_affinity=function_args.get("canopy_affinity"),
                edge_affinity=function_args.get("edge_affinity"),
                moisture_affinity=function_args.get("moisture_affinity"),
                disturbance_affinity=function_args.get("disturbance_affinity"),
                limit=function_args.get("limit", 400),
                weight=weight,
            )
        else:
            return {"error": f"Unknown function: {function_name}"}

    async def _search_by_image_similarity(
        self, reference_species: str, weight: float, limit: int = 50
    ) -> list[dict]:
        """
        Find species visually similar to a reference species using image embeddings.

        Args:
            reference_species: Scientific name of the reference species
            weight: Pre-normalized scoring weight for this tool
            limit: Maximum number of similar images to retrieve

        Returns:
            List of dicts with keys [imgId, species, score, tool_names]
        """
        scientific_name = (reference_species or "").strip()
        if not scientific_name:
            logger.warning("search_by_image_similarity called with empty species name")
            return []

        image_ids = self.image_meta_service.get_image_ids_by_species(scientific_name)
        if not image_ids:
            logger.info(f"No images found for reference species: {scientific_name}")
            return []

        similar_images: pl.DataFrame = self.image_service.find_similar_images(
            image_ids=image_ids, limit=limit
        )

        if similar_images is None or similar_images.is_empty():
            logger.info(f"No similar images found for species: {scientific_name}")
            return []

        return self._build_result_df(
            df=similar_images,
            score_expr=pl.lit(weight) * (1 - pl.col("distance")),
            tool_name="search_by_image_similarity",
        ).to_dicts()

    async def _search_by_location(
        self, location: str, weight: float, limit: int = 100
    ) -> list[dict]:
        """
        Search for species occurring in a specific geographic location via GBIF.

        Args:
            location: Country or region name
            weight: Pre-normalized scoring weight for this tool
            limit: Maximum number of species to return

        Returns:
            List of dicts with keys [imgId, species, score, tool_names]
        """
        if not location:
            logger.warning("search_by_location called with empty location")
            return []

        species_names = self.gbif_service.search_by_location(
            location=location, limit=limit
        )
        logger.info(f"Location search found {len(species_names)} species for '{location}'")

        unique_species = list(set(species_names))
        data = self.image_meta_service.get_species_main_image_id_from_list(unique_species)

        if data is None or data.is_empty():
            return []

        return self._build_result_df(
            df=data,
            score_expr=pl.lit(weight),
            tool_name="search_by_location",
        ).to_dicts()

    async def _search_by_color(
        self, color_description: str, weight: float, limit: int = 50
    ) -> list[dict]:
        """
        Search for species matching a color description using CLIP embeddings.

        Fetches 10x images (min 300) to ensure species diversity after aggregation,
        then deduplicates by species keeping the best (lowest distance) match.

        Args:
            color_description: Natural language color description (e.g., "blue", "orange spots")
            weight: Pre-normalized scoring weight for this tool
            limit: Target number of species to return

        Returns:
            List of dicts with keys [imgId, species, score, tool_names]
        """
        if not color_description:
            logger.warning("search_by_color called with empty color description")
            return []

        image_limit = max(limit * 10, 300)

        raw_results = self.image_service.fetch_similar_images_from_text(
            request=self.request,
            text=color_description,
            limit=image_limit,
        )

        if not raw_results:
            return []

        # Accept both list-of-dicts and DataFrame from the image service
        results_df = (
            raw_results
            if isinstance(raw_results, pl.DataFrame)
            else pl.DataFrame(raw_results)
        )

        if results_df.is_empty():
            return []

        # Deduplicate by species: keep row with lowest distance (best color match)
        results_df = (
            results_df.sort("distance")
            .unique(subset=["species"], keep="first")
        )

        return self._build_result_df(
            df=results_df,
            score_expr=pl.lit(weight) * (1 - pl.col("distance") / 2),
            tool_name="search_by_color",
        ).to_dicts()

    async def _search_by_traits(
        self,
        canopy_affinity: str = None,
        edge_affinity: str = None,
        moisture_affinity: str = None,
        disturbance_affinity: str = None,
        limit: int = 100,
        weight: float = 0.25,
    ) -> list[dict]:
        """
        Search species by habitat preferences and ecological traits (AND logic).

        Args:
            canopy_affinity: "High", "Medium", or "Low"
            edge_affinity: "High", "Medium", or "Low"
            moisture_affinity: "High", "Medium", or "Low"
            disturbance_affinity: "High", "Medium", or "Low"
            limit: Maximum number of species to return
            weight: Pre-normalized scoring weight for this tool

        Returns:
            List of dicts with keys [imgId, species, score, tool_names]
        """
        conditions = []
        if canopy_affinity:
            conditions.append(f"CanopyAffinity = '{canopy_affinity}'")
        if edge_affinity:
            conditions.append(f"EdgeAffinity = '{edge_affinity}'")
        if moisture_affinity:
            conditions.append(f"MoistureAffinity = '{moisture_affinity}'")
        if disturbance_affinity:
            conditions.append(f"DisturbanceAffinity = '{disturbance_affinity}'")

        if not conditions:
            logger.warning("search_by_traits called with no trait conditions")
            return []

        where_clause = " AND ".join(conditions)
        query = (
            f"SELECT DISTINCT Species FROM {self.leptraits_service.table} "
            f"WHERE {where_clause} LIMIT {limit}"
        )

        result = self.leptraits_service.db_client.execute(query).pl()
        if result.is_empty():
            return []

        species_names = result["Species"].to_list()
        unique_species = list(set(species_names))

        data = self.image_meta_service.get_species_main_image_id_from_list(unique_species)
        if data is None or data.is_empty():
            return []

        return self._build_result_df(
            df=data,
            score_expr=pl.lit(weight),
            tool_name="search_by_traits",
        ).to_dicts()

    def _build_result_df(
        self,
        df: pl.DataFrame,
        score_expr: pl.Expr,
        tool_name: str,
    ) -> pl.DataFrame:
        """
        Standardize a search result DataFrame into the canonical output format.

        All tool results are normalized to the same 4-column schema before
        being passed to _aggregate_results.

        Args:
            df: Input DataFrame ? must contain 'imgId' and 'species' columns
            score_expr: Polars expression computing the score for each row
            tool_name: Internal tool identifier string (e.g., "search_by_color")

        Returns:
            pl.DataFrame with columns [imgId, species, score, tool_names]
        """
        return (
            df.with_columns(
                score_expr.alias("score"),
                pl.lit(tool_name).alias("tool_names"),
            )
            .select(["imgId", "species", "score", "tool_names"])
        )

    def _get_tools(self) -> List[Dict]:
        """
        Define available tools for OpenAI function calling.

        Returns:
            List of tool definitions in OpenAI function calling format.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_by_image_similarity",
                    "description": (
                        "Finds species visually similar to a specific scientific name. "
                        "Use when the user asks for species that look like, resemble, or are "
                        "similar in appearance to a known species. "
                        "Example: 'butterflies similar to Danaus plexippus'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reference_species": {
                                "type": "string",
                                "description": (
                                    "Scientific name of the reference species "
                                    "(e.g., 'Danaus plexippus'). Convert common names "
                                    "to scientific names if possible."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "default": 50,
                                "description": "Maximum number of similar images to retrieve",
                            },
                        },
                        "required": ["reference_species"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_location",
                    "description": (
                        "Finds species occurring in a specific country or geographic region. "
                        "Use when the user specifies a location constraint. "
                        "Example: 'butterflies in Brazil', 'species from Costa Rica'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": (
                                    "Country or region name (e.g., 'Brazil', 'Costa Rica', "
                                    "'Amazon'). Use standardized country names when possible."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "default": 500,
                                "description": "Maximum number of species to return",
                            },
                        },
                        "required": ["location"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_color",
                    "description": (
                        "Finds species matching color or pattern descriptions using image analysis. "
                        "Use when the user describes colors, patterns, or visual appearance. "
                        "Example: 'blue butterflies', 'orange spots', 'iridescent wings'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "color_description": {
                                "type": "string",
                                "description": (
                                    "Natural language color or pattern description. "
                                    "Can be simple ('blue') or complex ('orange and black stripes')"
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "default": 150,
                                "description": "Target number of species to return",
                            },
                        },
                        "required": ["color_description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_traits",
                    "description": (
                        "Finds species by ecological traits and habitat preferences. "
                        "Use when the user specifies habitat characteristics. "
                        "Example: 'species with high canopy affinity', 'disturbance-tolerant butterflies'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "canopy_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for canopy cover. High = dense canopy, Low = open areas",
                            },
                            "edge_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for habitat edges. High = edge specialist, Low = interior specialist",
                            },
                            "moisture_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for moisture. High = wet habitats, Low = dry habitats",
                            },
                            "disturbance_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Tolerance of habitat disturbance. High = disturbance-tolerant, Low = sensitive",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Maximum number of species to return",
                            },
                        },
                        # No required parameters ? any combination of traits is valid
                    },
                },
            },
        ]