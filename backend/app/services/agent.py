"""
Agent-based semantic search service for biodiversity data.
"""

import logging
import json
import asyncio

import polars as pl

from typing import List, Dict, Any, Optional

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
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    species: str
    tool_calls: List[str]
    score: float = 0.0

    @field_serializer("score")
    def serialize_score(self, score: float) -> float:
        return round(score, 4)


class AgentSearchService:
    """
    Two-phase agent search service:

    Phase 1 ? Filter: location + traits tools run in parallel, results intersected
                      to form a species allowlist.
    Phase 2 ? Rank:   color + similarity tools run scoped to allowlist image IDs.
                      If no ranking tools, filter scores are used directly.

    Scoring:
        Equal weight = 1.0 / num_invoked_tools assigned to each tool.
        Color/similarity scores: weight * (1 - distance / 2) or weight * (1 - distance)
        Filter scores: weight * 1.0 (binary match)
        Penalty: 0.15 * (num_tools - tools_matched) applied per species at aggregation.
    """

    TOOL_PENALTY = 0.15

    FILTER_TOOLS  = {"search_by_location", "search_by_traits"}
    RANKING_TOOLS = {"search_by_color", "search_by_image_similarity"}

    def __init__(self, request: Request):
        config = OpenAIConfig()
        if not config.api_key or not config.api_url:
            raise ValueError("OpenAI API key and URL must be configured for agent search")

        self.client = OpenAI(base_url=config.api_url, api_key=config.api_key)
        self.model  = config.model or "gpt-4o"
        self.request = request

        self.image_service = ImagePersistData(
            lance_db=request.app.state.lance_db,
            duckdb=request.app.state.duck_db,
        )
        self.image_meta_service = ImageMetaService(duckdb=request.app.state.duck_db)
        self.gbif_service       = GbifPersistData(duckdb=request.app.state.duck_db)
        self.leptraits_service  = LepTraits(duckdb=request.app.state.duck_db)


    async def search(self, query: str) -> pl.DataFrame:
        """
        Two-phase search pipeline:

        Phase 1 ? Filter: Run location and/or traits tools in parallel.
                        Intersect their species sets to form an allowlist.
                        Results are cached to avoid re-execution.

        Phase 2 ? Rank:   If ranking tools (color, similarity) were requested,
                        run them scoped to allowlist image IDs only.
                        Ranking tools share 100% of the score weight when
                        filter tools are also active (filter tools gate the
                        pool but do not contribute to score).
                        If no ranking tools, filter tool scores are used directly.

        Scoring:
            - ranking + filter tools: each ranking tool gets weight = 1.0 / num_ranking_tools
            - ranking tools only:     each ranking tool gets weight = 1.0 / num_ranking_tools
            - filter tools only:      each filter tool gets weight  = 1.0 / num_filter_tools

        Args:
            query: Natural language search query

        Returns:
            pl.DataFrame with columns [imgId, species, score, tool_names]
            sorted by score descending. Empty DataFrame if no results.

        Raises:
            Exception: If OpenAI API call fails (logged and re-raised)
        """
        tools    = self._get_tools()
        messages = self._build_messages(query)

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

            # Split by role
            filter_calls  = [c for c in parsed_calls if c["name"] in self.FILTER_TOOLS]
            ranking_calls = [c for c in parsed_calls if c["name"] in self.RANKING_TOOLS]

            logger.info(
                f"Filter tools: {[c['name'] for c in filter_calls]} | "
                f"Ranking tools: {[c['name'] for c in ranking_calls]}"
            )

            # ?? Compute normalized weights ????????????????????????????????????????
            # When ranking tools are present, they own 100% of the score.
            # Filter tools only gate the candidate pool ? they never contribute to score.
            # When only filter tools are present, they share the full score weight.
            normalized_weights: Dict[str, float] = {}

            if ranking_calls:
                # Ranking tools share 1.0 equally regardless of how many filter tools fired
                num_ranking = len({c["name"] for c in ranking_calls})
                ranking_weight = 1.0 / num_ranking if num_ranking > 0 else 1.0
                for c in ranking_calls:
                    normalized_weights[c["name"]] = ranking_weight
                for c in filter_calls:
                    normalized_weights[c["name"]] = 0.0  # filter tools don't score
            else:
                # Filter-only query ? filter tools share the full weight
                num_filter = len({c["name"] for c in filter_calls})
                filter_weight = 1.0 / num_filter if num_filter > 0 else 1.0
                for c in filter_calls:
                    normalized_weights[c["name"]] = filter_weight

            logger.info(f"Normalized weights: {normalized_weights}")

            # ?? Phase 1: Run filter tools in parallel, build allowlist ????????????
            # allowlist_species = None means no filter applied (ranking-only query)
            allowlist_species: Optional[set[str]] = None
            cached_filter_rows: Dict[str, List[Dict]] = {}

            if filter_calls:
                filter_results = await asyncio.gather(
                    *[
                        self._execute_tool(
                            c["name"], c["args"],
                            normalized_weights.get(c["name"], 0.0),
                        )
                        for c in filter_calls
                    ],
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
                    logger.info(
                        f"Filter tool '{tool_name}' returned {len(species_set)} species"
                    )

                if per_tool_species:
                    # Intersect all filter tool species sets
                    allowlist_species = per_tool_species[0].intersection(*per_tool_species[1:])
                    logger.info(
                        f"Allowlist after intersection of {len(per_tool_species)} "
                        f"filter tools: {len(allowlist_species)} species"
                    )

                    # Fall back to union if intersection is empty
                    if not allowlist_species:
                        logger.warning(
                            "Filter intersection produced 0 species ? falling back to union"
                        )
                        allowlist_species = set().union(*per_tool_species)
                        logger.info(f"Union fallback: {len(allowlist_species)} species")

            # ?? Phase 2: Score results ????????????????????????????????????????????
            all_results:       List[Dict] = []
            active_tool_names: List[str]  = []

            if ranking_calls:
                # Build allowlist_img_ids scoped to allowlisted species
                allowlist_img_ids: Optional[List[str]] = None

                if allowlist_species is not None:
                    # Seed with imgIds already returned by filter tools
                    img_id_set: set[str] = {
                        row["imgId"]
                        for call in filter_calls
                        for row in cached_filter_rows.get(call["name"], [])
                        if row["species"] in allowlist_species and row.get("imgId")
                    }

                    # Supplement from DB if coverage is sparse
                    # (filter tools return one main image per species; color search
                    #  needs more images to find the best color match)
                    if len(img_id_set) < len(allowlist_species) * 3:
                        db_img_ids = self.image_meta_service.get_image_ids_for_species_list(
                            list(allowlist_species)
                        )
                        img_id_set.update(db_img_ids)

                    allowlist_img_ids = list(img_id_set)

                    if not allowlist_img_ids:
                        logger.warning(
                            "No image IDs found for allowlisted species ? "
                            "cannot scope ranking tools"
                        )
                        return pl.DataFrame()

                # Execute each ranking tool, scoped to allowlist or full index
                for call in ranking_calls:
                    weight = normalized_weights.get(call["name"], 1.0)

                    if allowlist_img_ids is not None:
                        rows = await self._execute_tool_scoped(
                            call["name"], call["args"],
                            allowlist_img_ids, allowlist_species, weight,
                        )
                    else:
                        # Ranking-only query ? search full index
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
                # Filter-only query ? filter tool scores ARE the final scores
                if allowlist_species is not None:
                    for call in filter_calls:
                        rows = cached_filter_rows.get(call["name"], [])
                        filtered_rows = [
                            r for r in rows if r["species"] in allowlist_species
                        ]
                        if filtered_rows:
                            active_tool_names.append(call["name"])
                            all_results.extend(filtered_rows)
                else:
                    logger.warning("No filter or ranking tools produced results")
                    return pl.DataFrame()

            if not all_results:
                logger.warning(f"No results collected for query: {query}")
                return pl.DataFrame()

            logger.info(
                f"Collected {len(all_results)} rows "
                f"from tools: {set(active_tool_names)}"
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

        aggregated = (
            df.group_by("species")
            .agg([
                # Prefer imgId from ranking tools (best visual match)
                pl.when(
                    pl.col("tool_names").is_in(
                        ["search_by_color", "search_by_image_similarity"]
                    )
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
                (
                    pl.col("score")
                    - self.TOOL_PENALTY * (num_tools_used - pl.col("tool_hit_count"))
                )
                .clip(0.0, 1.0)
                .alias("score")
            )
            .drop("tool_hit_count")
            .sort("score", descending=True)
        )

        logger.info(
            f"Aggregated {len(df)} rows ? {len(aggregated)} unique species | "
            f"top score: {aggregated['score'][0]:.4f}"
        )
        return aggregated

    # ?? Tool execution ????????????????????????????????????????????????????????

    async def _execute_tool(
        self, function_name: str, function_args: Dict[str, Any], weight: float
    ) -> list[dict]:
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

    async def _execute_tool_scoped(
        self,
        function_name: str,
        function_args: Dict[str, Any],
        allowlist_img_ids: List[str],
        allowlist_species: set[str],
        weight: float,
    ) -> list[dict]:
        if function_name == "search_by_color":
            color_description = function_args.get("color_description", "")
            if not color_description:
                return []

            image_limit = max(function_args.get("limit", 150) * 10, 300)
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

            results_df = results_df.filter(
                pl.col("species").is_in(list(allowlist_species))
            )
            if results_df.is_empty():
                return []

            results_df = results_df.sort("distance").unique(
                subset=["species"], keep="first"
            )

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

            similar_images = self.image_service.find_similar_images(
                image_ids=image_ids,
                limit=function_args.get("limit", 400),
            )
            if similar_images is None or similar_images.is_empty():
                return []

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

    # Search methods ------------------------

    async def _search_by_image_similarity(
        self, reference_species: str, weight: float, limit: int = 50
    ) -> list[dict]:
        scientific_name = (reference_species or "").strip()
        if not scientific_name:
            logger.warning("search_by_image_similarity called with empty species name")
            return []

        image_ids = self.image_meta_service.get_image_ids_by_species(scientific_name)
        if not image_ids:
            return []

        similar_images = self.image_service.find_similar_images(
            image_ids=image_ids, limit=limit
        )
        if similar_images is None or similar_images.is_empty():
            return []

        return self._build_result_df(
            df=similar_images,
            score_expr=pl.lit(weight) * (1 - pl.col("distance")),
            tool_name="search_by_image_similarity",
        ).to_dicts()

    async def _search_by_location(
        self, location: str, weight: float, limit: int = 100
    ) -> list[dict]:
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

        results_df = (
            raw_results
            if isinstance(raw_results, pl.DataFrame)
            else pl.DataFrame(raw_results)
        )
        if results_df.is_empty():
            return []

        results_df = results_df.sort("distance").unique(
            subset=["species"], keep="first"
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
        sql = (
            f"SELECT DISTINCT Species FROM {self.leptraits_service.table} "
            f"WHERE {where_clause} LIMIT {limit}"
        )

        result = self.leptraits_service.db_client.execute(sql).pl()
        if result.is_empty():
            return []

        unique_species = list(set(result["Species"].to_list()))
        data = self.image_meta_service.get_species_main_image_id_from_list(unique_species)
        if data is None or data.is_empty():
            return []

        return self._build_result_df(
            df=data,
            score_expr=pl.lit(weight),
            tool_name="search_by_traits",
        ).to_dicts()

    # Helpers ------------------------

    def _build_result_df(
        self, df: pl.DataFrame, score_expr: pl.Expr, tool_name: str
    ) -> pl.DataFrame:
        return (
            df.with_columns(
                score_expr.alias("score"),
                pl.lit(tool_name).alias("tool_names"),
            )
            .select(["imgId", "species", "score", "tool_names"])
        )

    def _build_messages(self, query: str) -> List[Dict]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a search router. Your ONLY job is to decompose the user's request into parallel tool calls. "
                    "Follow these decomposition rules strictly:\n"
                    "1. VISUALS: If the query contains colors (e.g., 'blue', 'orange'), patterns ('spotted'), or visual descriptions, you MUST call 'search_by_color'.\n"
                    "2. LOCATION: If the query contains a country or region (e.g., 'Brazil', 'Indonesia'), you MUST call 'search_by_location'. "
                    "The 'location' argument MUST be the ISO 3166-1 alpha-2 country code "
                    "(e.g., 'Brazil' ? 'BR', 'Indonesia' ? 'ID', 'Costa Rica' ? 'CR'). "
                    "If the location is a region (e.g., 'Amazon', 'Southeast Asia') with no single country code, use the most representative country code.\n"
                    "3. TRAITS: If the query mentions habitat (e.g., 'canopy', 'dry'), call 'search_by_traits'.\n"
                    "4. COMBINATION: For queries like 'Blue butterfly in Brazil', you MUST call BOTH "
                    "'search_by_color' (arg: 'blue') AND 'search_by_location' (arg: 'BR').\n"
                    "5. FILTERING: Ignore generic terms like 'butterfly', 'insect', or 'species'. Focus ONLY on the distinguishing attributes.\n"
                    "6. SPECIFIC NAMES: Only use 'search_by_image_similarity' if the user specifically asks for species 'similar to' a scientific name."
                ),
            },
            {"role": "user", "content": query},
        ]

    def _get_tools(self) -> List[Dict]:
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
                        "Example: 'butterflies in Brazil' ? location='BR', "
                        "'species from Indonesia' ? location='ID'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": (
                                    "ISO 3166-1 alpha-2 country code "
                                    "(e.g., 'BR' for Brazil, 'ID' for Indonesia, "
                                    "'CR' for Costa Rica). Always convert country "
                                    "names to their 2-letter ISO code."
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
                        "Example: 'species with high canopy affinity', "
                        "'disturbance-tolerant butterflies'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "canopy_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for canopy cover",
                            },
                            "edge_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for habitat edges",
                            },
                            "moisture_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Preference for moisture",
                            },
                            "disturbance_affinity": {
                                "type": "string",
                                "enum": ["High", "Medium", "Low"],
                                "description": "Tolerance of habitat disturbance",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Maximum number of species to return",
                            },
                        },
                    },
                },
            },
        ]
