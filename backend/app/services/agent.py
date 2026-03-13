"""
Agent-based semantic search service for biodiversity data.
"""

import logging
import json
import asyncio
from typing import List, Dict, Any

import polars as pl
from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel
from fastapi import Request
from openai import OpenAI

from .image_meta import ImageMetaService
from ..configs.config import OpenAIConfig, PromptsConfig
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
    Two-phase agent search service.

    Phase 1 ? Filter:
        Location + traits tools run in parallel; their species sets are
        intersected (with union fallback) to form a species allowlist.

    Phase 2 ? Rank:
        Color + similarity tools run scoped to allowlist image IDs.
        If no ranking tools are invoked, filter scores are used directly.

    Scoring:
        - Ranking tools present  ? each ranking tool weight = 1.0 / num_ranking_tools;
                                   filter tools contribute 0 to score (gate only).
        - Filter tools only      ? each filter tool weight  = 1.0 / num_filter_tools;
                                   binary match score.
        - Penalty: 0.15 × (total_tools_invoked ? tools_matched_for_species),
                   clipped to [0.0, 1.0].
    """

    TOOL_PENALTY = 0.15
    FILTER_TOOLS = {"search_by_location", "search_by_traits"}
    RANKING_TOOLS = {"search_by_color", "search_by_image_similarity"}

    def __init__(self, request: Request) -> None:
        config = OpenAIConfig()
        if not config.api_key or not config.api_url:
            raise ValueError(
                "OpenAI API key and URL must be configured for agent search."
            )

        self.client = OpenAI(base_url=config.api_url, api_key=config.api_key)
        self.model = config.model or "gpt-4o"
        self.request = request

        prompts = PromptsConfig()
        self.system_prompt = prompts.router_agent
        self.tool_definitions = [
            prompts.build_tool_definition(prompts.image_similarity),
            prompts.build_tool_definition(prompts.location_search),
            prompts.build_tool_definition(prompts.color_search),
            prompts.build_tool_definition(prompts.trait_search),
        ]

        self.image_service = ImagePersistData(
            lance_db=request.app.state.lance_db,
            duckdb=request.app.state.duck_db,
        )
        self.image_meta_service = ImageMetaService(duckdb=request.app.state.duck_db)
        self.gbif_service = GbifPersistData(duckdb=request.app.state.duck_db)
        self.leptraits_service = LepTraits(duckdb=request.app.state.duck_db)

    async def search(self, query: str) -> pl.DataFrame:
        """
        Execute the two-phase search pipeline for *query*.

        Returns:
            pl.DataFrame with columns [imgId, species, score, tool_names],
            sorted by score descending. Empty DataFrame on no results.

        Raises:
            Exception: propagated from the OpenAI API call (logged first).
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                tools=self.tool_definitions,
                tool_choice="auto",
                timeout=30.0,
            )
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc, exc_info=True)
            raise

        message = response.choices[0].message
        if not message.tool_calls:
            logger.warning("LLM made no tool calls for query: %s", query)
            return pl.DataFrame()

        parsed_calls: List[Dict[str, Any]] = []
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.error("Failed to parse args for tool '%s'", tc.function.name)
                continue
            parsed_calls.append({"name": tc.function.name, "args": args})

        if not parsed_calls:
            logger.warning("All tool call arguments failed to parse.")
            return pl.DataFrame()

        filter_calls = [c for c in parsed_calls if c["name"] in self.FILTER_TOOLS]
        ranking_calls = [c for c in parsed_calls if c["name"] in self.RANKING_TOOLS]

        logger.info(
            "Filter tools: %s | Ranking tools: %s",
            [c["name"] for c in filter_calls],
            [c["name"] for c in ranking_calls],
        )

        normalized_weights: Dict[str, float] = {}
        if ranking_calls:
            num_ranking = len({c["name"] for c in ranking_calls})
            ranking_weight = 1.0 / num_ranking
            for c in ranking_calls:
                normalized_weights[c["name"]] = ranking_weight
            for c in filter_calls:
                normalized_weights[c["name"]] = 0.0
        else:
            num_filter = len({c["name"] for c in filter_calls})
            filter_weight = 1.0 / num_filter if num_filter else 1.0
            for c in filter_calls:
                normalized_weights[c["name"]] = filter_weight

        logger.info("Normalized weights: %s", normalized_weights)

        allowlist_species: set[str] | None = None
        cached_filter_rows: Dict[str, List[Dict]] = {}

        if filter_calls:
            filter_results = await asyncio.gather(
                *[
                    self._execute_tool(
                        c["name"],
                        c["args"],
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
                    logger.error("Filter tool '%s' raised: %s", tool_name, result)
                    continue
                if not result:
                    logger.warning("Filter tool '%s' returned empty result.", tool_name)
                    continue

                cached_filter_rows[tool_name] = result
                species_set = {row["species"] for row in result}
                per_tool_species.append(species_set)
                logger.info(
                    "Filter tool '%s' ? %d species", tool_name, len(species_set)
                )

            if per_tool_species:
                allowlist_species = per_tool_species[0].intersection(
                    *per_tool_species[1:]
                )
                logger.info(
                    "Allowlist after intersection of %d filter tool(s): %d species",
                    len(per_tool_species),
                    len(allowlist_species),
                )
                if not allowlist_species:
                    logger.warning("Intersection empty ? falling back to union.")
                    allowlist_species = set().union(*per_tool_species)
                    logger.info("Union fallback: %d species", len(allowlist_species))

        all_results: List[Dict] = []
        active_tool_names: List[str] = []

        if ranking_calls:
            allowlist_img_ids: list[str] | None = None

            if allowlist_species is not None:
                img_id_set: set[str] = {
                    row["imgId"]
                    for call in filter_calls
                    for row in cached_filter_rows.get(call["name"], [])
                    if row["species"] in allowlist_species and row.get("imgId")
                }
                if len(img_id_set) < len(allowlist_species) * 3:
                    db_ids = await asyncio.to_thread(
                        self.image_meta_service.get_image_ids_for_species_list,
                        list(allowlist_species),
                    )
                    img_id_set.update(db_ids)

                if not img_id_set:
                    logger.warning("No image IDs found for allowlisted species.")
                    return pl.DataFrame()

                allowlist_img_ids = list(img_id_set)

            for call in ranking_calls:
                weight = normalized_weights.get(call["name"], 1.0)
                if allowlist_img_ids is not None:
                    rows = await self._execute_tool_scoped(
                        call["name"],
                        call["args"],
                        allowlist_img_ids,
                        allowlist_species,
                        weight,  # type: ignore[arg-type]
                    )
                else:
                    rows = await self._execute_tool(call["name"], call["args"], weight)

                if isinstance(rows, Exception) or not rows:
                    logger.warning(
                        "Ranking tool '%s' returned no results.", call["name"]
                    )
                    continue

                active_tool_names.append(call["name"])
                all_results.extend(rows)

        else:
            if allowlist_species is None:
                logger.warning("No filter or ranking tools produced results.")
                return pl.DataFrame()

            for call in filter_calls:
                rows = [
                    r
                    for r in cached_filter_rows.get(call["name"], [])
                    if r["species"] in allowlist_species
                ]
                if rows:
                    active_tool_names.append(call["name"])
                    all_results.extend(rows)

        if not all_results:
            logger.warning("No results collected for query: %s", query)
            return pl.DataFrame()

        logger.info(
            "Collected %d rows from tools: %s",
            len(all_results),
            set(active_tool_names),
        )
        return self._aggregate_results(all_results, active_tool_names)

    def _aggregate_results(
        self, results: List[Dict], active_tool_names: List[str]
    ) -> pl.DataFrame:
        if not results:
            return pl.DataFrame()

        df = pl.DataFrame(results)

        expected_cols = {"imgId", "species", "score", "tool_names"}
        missing = expected_cols - set(df.columns)
        if missing:
            logger.error("Result rows missing expected columns: %s", missing)
            return pl.DataFrame()

        num_tools_used = len(set(active_tool_names))
        ranking_tool_names = list(self.RANKING_TOOLS)

        aggregated = (
            df.group_by("species")
            .agg(
                [
                    pl.when(pl.col("tool_names").is_in(ranking_tool_names))
                    .then(pl.col("imgId"))
                    .otherwise(None)
                    .drop_nulls()
                    .first()
                    .fill_null(pl.col("imgId").first())
                    .alias("imgId"),
                    pl.col("score").sum().alias("score"),
                    pl.col("tool_names").unique().alias("tool_names"),
                    pl.col("tool_names").n_unique().alias("tool_hit_count"),
                ]
            )
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
            "Aggregated %d rows ? %d unique species | top score: %.4f",
            len(df),
            len(aggregated),
            aggregated["score"][0],
        )
        return aggregated

    async def _execute_tool(
        self,
        function_name: str,
        function_args: Dict[str, Any],
        weight: float,
    ) -> list[dict]:
        dispatch = {
            "search_by_image_similarity": lambda: self._search_by_image_similarity(
                reference_species=function_args.get("reference_species", ""),
                weight=weight,
                limit=function_args.get("limit", 400),
            ),
            "search_by_location": lambda: self._search_by_location(
                location=function_args.get("location", ""),
                weight=weight,
                limit=function_args.get("limit", 400),
            ),
            "search_by_color": lambda: self._search_by_color(
                color_description=function_args.get("color_description", ""),
                weight=weight,
                limit=function_args.get("limit", 50),
            ),
            "search_by_traits": lambda: self._search_by_traits(
                canopy_affinity=function_args.get("canopy_affinity"),
                edge_affinity=function_args.get("edge_affinity"),
                moisture_affinity=function_args.get("moisture_affinity"),
                disturbance_affinity=function_args.get("disturbance_affinity"),
                limit=function_args.get("limit", 400),
                weight=weight,
            ),
        }
        handler = dispatch.get(function_name)
        if handler is None:
            logger.error("_execute_tool: unknown function '%s'", function_name)
            return []
        return await handler()

    async def _execute_tool_scoped(
        self,
        function_name: str,
        function_args: Dict[str, Any],
        allowlist_img_ids: list[str],
        allowlist_species: set[str],
        weight: float,
    ) -> list[dict]:
        if function_name == "search_by_color":
            color_description = function_args.get("color_description", "").strip()
            if not color_description:
                return []

            image_limit = max(function_args.get("limit", 150) * 10, 300)
            raw = await asyncio.to_thread(
                self.image_service.fetch_similar_images_from_text_filtered,
                self.request,
                color_description,
                image_limit,
                allowlist_img_ids,
            )
            if not raw:
                return []

            df = raw if isinstance(raw, pl.DataFrame) else pl.DataFrame(raw)
            if df.is_empty():
                return []

            df = (
                df.filter(pl.col("species").is_in(list(allowlist_species)))
                .sort("distance")
                .unique(subset=["species"], keep="first")
            )
            if df.is_empty():
                return []

            return self._build_result_df(
                df=df,
                score_expr=pl.lit(weight) * (1 - pl.col("distance") / 2),
                tool_name="search_by_color",
            ).to_dicts()

        elif function_name == "search_by_image_similarity":
            reference_species = (function_args.get("reference_species") or "").strip()
            if not reference_species:
                return []

            image_ids = await asyncio.to_thread(
                self.image_meta_service.get_image_ids_by_species,
                reference_species,
            )
            if not image_ids:
                return []

            similar = await asyncio.to_thread(
                self.image_service.find_similar_images,
                image_ids,
                function_args.get("limit", 400),
            )
            if similar is None or similar.is_empty():
                return []

            similar = similar.filter(pl.col("species").is_in(list(allowlist_species)))
            if similar.is_empty():
                return []

            return self._build_result_df(
                df=similar,
                score_expr=pl.lit(weight) * (1 - pl.col("distance")),
                tool_name="search_by_image_similarity",
            ).to_dicts()

        else:
            logger.error(
                "_execute_tool_scoped: unsupported function '%s'", function_name
            )
            return []

    async def _search_by_image_similarity(
        self,
        reference_species: str,
        weight: float,
        limit: int = 50,
    ) -> list[dict]:
        scientific_name = reference_species.strip()
        if not scientific_name:
            logger.warning("search_by_image_similarity called with empty species name.")
            return []

        image_ids = await asyncio.to_thread(
            self.image_meta_service.get_image_ids_by_species,
            scientific_name,
        )
        if not image_ids:
            return []

        similar = await asyncio.to_thread(
            self.image_service.find_similar_images,
            image_ids,
            limit,
        )
        if similar is None or similar.is_empty():
            return []

        return self._build_result_df(
            df=similar,
            score_expr=pl.lit(weight) * (1 - pl.col("distance")),
            tool_name="search_by_image_similarity",
        ).to_dicts()

    async def _search_by_location(
        self,
        location: str,
        weight: float,
        limit: int = 100,
    ) -> list[dict]:
        if not location:
            logger.warning("search_by_location called with empty location.")
            return []

        species_names = await asyncio.to_thread(
            self.gbif_service.search_by_location,
            location,
            limit,
        )
        logger.info("Location '%s' ? %d species", location, len(species_names))

        unique_species = list(set(species_names))
        data = await asyncio.to_thread(
            self.image_meta_service.get_species_main_image_id_from_list,
            unique_species,
        )
        if data is None or data.is_empty():
            return []

        return self._build_result_df(
            df=data,
            score_expr=pl.lit(weight),
            tool_name="search_by_location",
        ).to_dicts()

    async def _search_by_color(
        self,
        color_description: str,
        weight: float,
        limit: int = 50,
    ) -> list[dict]:
        if not color_description:
            logger.warning("search_by_color called with empty color description.")
            return []

        image_limit = max(limit * 10, 300)
        raw = await asyncio.to_thread(
            self.image_service.fetch_similar_images_from_text,
            self.request,
            color_description,
            image_limit,
        )
        if not raw:
            return []

        df = raw if isinstance(raw, pl.DataFrame) else pl.DataFrame(raw)
        if df.is_empty():
            return []

        df = df.sort("distance").unique(subset=["species"], keep="first")
        return self._build_result_df(
            df=df,
            score_expr=pl.lit(weight) * (1 - pl.col("distance") / 2),
            tool_name="search_by_color",
        ).to_dicts()

    async def _search_by_traits(
        self,
        canopy_affinity: str | None = None,
        edge_affinity: str | None = None,
        moisture_affinity: str | None = None,
        disturbance_affinity: str | None = None,
        limit: int = 100,
        weight: float = 0.25,
    ) -> list[dict]:
        conditions: list[str] = []
        if canopy_affinity:
            conditions.append(f"CanopyAffinity = '{canopy_affinity}'")
        if edge_affinity:
            conditions.append(f"EdgeAffinity = '{edge_affinity}'")
        if moisture_affinity:
            conditions.append(f"MoistureAffinity = '{moisture_affinity}'")
        if disturbance_affinity:
            conditions.append(f"DisturbanceAffinity = '{disturbance_affinity}'")

        if not conditions:
            logger.warning("search_by_traits called with no trait conditions.")
            return []

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT DISTINCT Species FROM {self.leptraits_service.table} "
            f"WHERE {where_clause} LIMIT {limit}"
        )

        result = await asyncio.to_thread(
            lambda: self.leptraits_service.db_client.execute(sql).pl()
        )
        if result.is_empty():
            return []

        unique_species = list(set(result["Species"].to_list()))
        data = await asyncio.to_thread(
            self.image_meta_service.get_species_main_image_id_from_list,
            unique_species,
        )
        if data is None or data.is_empty():
            return []

        return self._build_result_df(
            df=data,
            score_expr=pl.lit(weight),
            tool_name="search_by_traits",
        ).to_dicts()

    @staticmethod
    def _build_result_df(
        df: pl.DataFrame,
        score_expr: pl.Expr,
        tool_name: str,
    ) -> pl.DataFrame:
        return df.with_columns(
            score_expr.alias("score"),
            pl.lit(tool_name).alias("tool_names"),
        ).select(["imgId", "species", "score", "tool_names"])
