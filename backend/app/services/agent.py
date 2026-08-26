"""Agent-based semantic search orchestration for biodiversity data."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import polars as pl
from fastapi import Request
from openai import APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from ..configs.config import OpenAIConfig, PromptsConfig
from .agent_tools import (
    AgentWarning,
    ColorArgs,
    ImageSimilarityArgs,
    LocationArgs,
    ParsedToolCall,
    TraitArgs,
    build_tool_definitions,
    build_tool_registry,
    parse_tool_calls,
)
from .gbif import GbifPersistData
from .images import ImagePersistData
from .leptraits import LepTraits
from .metadata import ImageMetaService

logger = logging.getLogger(__name__)

RESULT_LIMIT = 50
VECTOR_CANDIDATE_LIMIT = 500
FILTER_SPECIES_LIMIT = 10_000
PLANNER_MAX_TOKENS = 512
PLANNER_TIMEOUT_SECONDS = 30.0
# Every ranked candidate already cleared the vector-search cutoff, so the
# weakest one in a pool is still a match and must not be reported as 0%.
RANKING_SCORE_FLOOR = 0.5


class AgentSearchResult(BaseModel):
    """Public result item returned by agent search."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    species: str
    score: float = 0.0
    tool_names: list[str] = Field(default_factory=list, alias="tool_names")

    @field_serializer("score")
    def serialize_score(self, score: float) -> float:
        return round(score, 4)


@dataclass
class AgentSearchOutcome:
    dataframe: pl.DataFrame
    warnings: list[AgentWarning]


ToolStatus = Literal["success", "error"]


@dataclass
class ToolExecution:
    call: ParsedToolCall
    status: ToolStatus
    rows: list[dict]
    error: Exception | None = None


class AgentSearchError(Exception):
    """Base exception for errors mapped by the agent-search router."""


class AgentConfigurationError(AgentSearchError):
    """The planner provider is not configured."""


class AgentPlannerError(AgentSearchError):
    """The planner returned an unusable response."""


class AgentPlannerTimeoutError(AgentPlannerError):
    """The planner exceeded its request timeout."""


class AgentToolFailureError(AgentSearchError):
    """Every selected tool failed before producing a valid outcome."""


class AgentSearchService:
    """Plan, filter, rank, and aggregate semantic species searches."""

    def __init__(
        self,
        request: Request,
        *,
        client: Any | None = None,
        model: str | None = None,
        image_service: ImagePersistData | None = None,
        image_meta_service: ImageMetaService | None = None,
        gbif_service: GbifPersistData | None = None,
        leptraits_service: LepTraits | None = None,
    ) -> None:
        config = OpenAIConfig()
        if client is None:
            if not config.api_key or not config.api_url:
                raise AgentConfigurationError(
                    "OpenAI-compatible API key and URL must be configured."
                )
            client = OpenAI(base_url=config.api_url, api_key=config.api_key)

        self.client = client
        self.model = model or config.model or "gpt-4o"
        self.request = request

        prompts = PromptsConfig()
        self.system_prompt = prompts.router_agent
        self.tool_registry = build_tool_registry(prompts)
        self.tool_definitions = build_tool_definitions(prompts, self.tool_registry)

        duckdb = request.app.state.duck_db
        self.image_service = image_service or ImagePersistData(
            lance_db=request.app.state.lance_db,
            duckdb=duckdb,
        )
        self.image_meta_service = image_meta_service or ImageMetaService(duckdb=duckdb)
        self.gbif_service = gbif_service or GbifPersistData(duckdb=duckdb)
        self.leptraits_service = leptraits_service or LepTraits(duckdb=duckdb)

    async def search(self, query: str) -> AgentSearchOutcome:
        """Run a single planner request followed by filter-first tool execution."""
        response = await self._plan(query)
        if not getattr(response, "choices", None):
            raise AgentPlannerError("The planner returned no choices.")

        message = response.choices[0].message
        raw_tool_calls = list(getattr(message, "tool_calls", None) or [])
        if not raw_tool_calls:
            logger.info("Planner selected no tools.")
            return AgentSearchOutcome(self._empty_results(), [])

        calls, warnings = parse_tool_calls(raw_tool_calls, self.tool_registry)
        if not calls:
            raise AgentPlannerError("The planner returned no valid tool calls.")

        filter_calls = [call for call in calls if call.category == "filter"]
        ranking_calls = [call for call in calls if call.category == "ranking"]

        filter_executions = [
            await self._execute_safely(call, allowlist_species=None)
            for call in filter_calls
        ]
        warnings.extend(self._execution_warnings(filter_executions))
        successful_filters = [
            execution
            for execution in filter_executions
            if execution.status == "success"
        ]

        # A successful empty filter is a hard constraint with no matches.
        if any(not execution.rows for execution in successful_filters):
            return AgentSearchOutcome(self._empty_results(), warnings)

        allowlist_species = self._intersect_filter_species(successful_filters)
        if allowlist_species == set():
            return AgentSearchOutcome(self._empty_results(), warnings)

        ranking_executions = [
            await self._execute_safely(call, allowlist_species)
            for call in ranking_calls
        ]
        warnings.extend(self._execution_warnings(ranking_executions))
        successful_rankings = [
            execution
            for execution in ranking_executions
            if execution.status == "success"
        ]

        successful_count = len(successful_filters) + len(successful_rankings)
        if successful_count == 0:
            raise AgentToolFailureError("Every selected search tool failed.")

        if ranking_calls:
            if successful_rankings:
                ranking_rows = [
                    row for execution in successful_rankings for row in execution.rows
                ]
                if not ranking_rows:
                    return AgentSearchOutcome(self._empty_results(), warnings)
                dataframe = self._aggregate_ranking_results(
                    ranking_rows,
                    filter_tool_names=[
                        execution.call.name for execution in successful_filters
                    ],
                )
                return AgentSearchOutcome(dataframe, warnings)

            # All rankings failed. Partial mode falls back to successful filters.
            if allowlist_species is not None and successful_filters:
                return AgentSearchOutcome(
                    self._build_filter_results(
                        allowlist_species,
                        successful_filters,
                    ),
                    warnings,
                )
            raise AgentToolFailureError("Every ranking tool failed.")

        if allowlist_species is None:
            raise AgentToolFailureError("No filter tool completed successfully.")
        return AgentSearchOutcome(
            self._build_filter_results(allowlist_species, successful_filters),
            warnings,
        )

    async def _plan(self, query: str) -> Any:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]
        try:
            return await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                tools=self.tool_definitions,
                tool_choice="auto",
                max_tokens=PLANNER_MAX_TOKENS,
                timeout=PLANNER_TIMEOUT_SECONDS,
            )
        except APITimeoutError as exc:
            logger.error("Planner request timed out.", exc_info=True)
            raise AgentPlannerTimeoutError("The planner request timed out.") from exc
        except Exception as exc:
            logger.error("Planner request failed.", exc_info=True)
            raise AgentPlannerError("The planner request failed.") from exc

    async def _execute_safely(
        self,
        call: ParsedToolCall,
        allowlist_species: set[str] | None,
    ) -> ToolExecution:
        try:
            rows = await self._execute_tool(call, allowlist_species)
            return ToolExecution(call=call, status="success", rows=rows)
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", call.name, exc, exc_info=True)
            return ToolExecution(call=call, status="error", rows=[], error=exc)

    @staticmethod
    def _execution_warnings(
        executions: list[ToolExecution],
    ) -> list[AgentWarning]:
        return [
            AgentWarning(
                code="tool_execution_failed",
                tool=execution.call.name,
                message="This search constraint could not be evaluated.",
            )
            for execution in executions
            if execution.status == "error"
        ]

    @staticmethod
    def _intersect_filter_species(
        executions: list[ToolExecution],
    ) -> set[str] | None:
        if not executions:
            return None
        species_sets = [
            {row["species"] for row in execution.rows} for execution in executions
        ]
        return set.intersection(*species_sets)

    async def _execute_tool(
        self,
        call: ParsedToolCall,
        allowlist_species: set[str] | None,
    ) -> list[dict]:
        if isinstance(call.args, ImageSimilarityArgs):
            return await self._search_by_image_similarity(
                call.args.reference_species,
                allowlist_species,
            )
        if isinstance(call.args, LocationArgs):
            return await self._search_by_location(
                call.args.normalized_location(),
            )
        if isinstance(call.args, ColorArgs):
            return await self._search_by_color(
                call.args.color_description,
                allowlist_species,
            )
        if isinstance(call.args, TraitArgs):
            return await self._search_by_traits(call.args)
        raise ValueError(f"Unsupported validated tool call: {call.name}")

    async def _search_by_image_similarity(
        self,
        reference_species: str,
        allowlist_species: set[str] | None,
    ) -> list[dict]:
        image_ids = await asyncio.to_thread(
            self.image_meta_service.get_image_ids_by_species,
            reference_species,
            raise_on_error=True,
        )
        if not image_ids:
            return []

        filter_img_ids = await self._allowlist_image_ids(allowlist_species)
        if allowlist_species is not None and not filter_img_ids:
            return []

        similar = await asyncio.to_thread(
            self.image_service.find_similar_images,
            image_ids,
            VECTOR_CANDIDATE_LIMIT,
            filter_img_ids,
            raise_on_error=True,
        )
        if similar is None or similar.is_empty():
            return []

        normalized_reference = self._normalize_species(reference_species)
        similar = similar.filter(
            pl.col("species")
            .cast(pl.String)
            .map_elements(self._normalize_species, return_dtype=pl.String)
            != normalized_reference
        )
        return self._build_ranking_rows(
            similar,
            tool_name="search_by_image_similarity",
        )

    async def _search_by_location(self, location: str) -> list[dict]:
        species_names = await asyncio.to_thread(
            self.gbif_service.search_by_country_code,
            location,
            FILTER_SPECIES_LIMIT,
        )
        return await self._species_to_filter_rows(
            species_names,
            tool_name="search_by_location",
        )

    async def _search_by_color(
        self,
        color_description: str,
        allowlist_species: set[str] | None,
    ) -> list[dict]:
        filter_img_ids = await self._allowlist_image_ids(allowlist_species)
        if allowlist_species is not None and not filter_img_ids:
            return []

        if filter_img_ids is None:
            raw = await asyncio.to_thread(
                self.image_service.fetch_similar_images_from_text,
                self.request,
                color_description,
                VECTOR_CANDIDATE_LIMIT,
                raise_on_error=True,
            )
        else:
            raw = await asyncio.to_thread(
                self.image_service.fetch_similar_images_from_text_filtered,
                self.request,
                color_description,
                VECTOR_CANDIDATE_LIMIT,
                filter_img_ids,
                raise_on_error=True,
            )
        if not raw:
            return []

        dataframe = raw if isinstance(raw, pl.DataFrame) else pl.DataFrame(raw)
        if dataframe.is_empty():
            return []
        dataframe = dataframe.sort("distance").unique(
            subset=["species"], keep="first", maintain_order=True
        )
        return self._build_ranking_rows(
            dataframe,
            tool_name="search_by_color",
        )

    async def _search_by_traits(self, args: TraitArgs) -> list[dict]:
        columns = {
            "canopy_affinity": "CanopyAffinity",
            "edge_affinity": "EdgeAffinity",
            "moisture_affinity": "MoistureAffinity",
            "disturbance_affinity": "DisturbanceAffinity",
        }
        conditions: list[str] = []
        params: list[Any] = []
        values = args.model_dump(exclude_none=True)
        for field_name, column_name in columns.items():
            if field_name in values:
                conditions.append(f"{column_name} = ?")
                params.append(values[field_name])

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT DISTINCT Species FROM {self.leptraits_service.table} "
            f"WHERE {where_clause} ORDER BY Species LIMIT ?"
        )
        params.append(FILTER_SPECIES_LIMIT)
        result = await asyncio.to_thread(
            self.leptraits_service.db_client.execute_prepared_to_pl,
            sql,
            params,
        )
        species_names = result["Species"].to_list() if not result.is_empty() else []
        return await self._species_to_filter_rows(
            species_names,
            tool_name="search_by_traits",
        )

    async def _species_to_filter_rows(
        self,
        species_names: list[str],
        *,
        tool_name: str,
    ) -> list[dict]:
        unique_species = sorted(
            {
                str(species).strip()
                for species in species_names
                if species and str(species).strip()
            }
        )
        if not unique_species:
            return []

        dataframe = await asyncio.to_thread(
            self.image_meta_service.get_species_main_image_id_from_list,
            unique_species,
            raise_on_error=True,
        )
        if dataframe is None or dataframe.is_empty():
            return []
        return (
            dataframe.sort(["species", "imgId"])
            .unique(subset=["species"], keep="first", maintain_order=True)
            .with_columns(pl.lit(tool_name).alias("tool_names"))
            .select(["imgId", "species", "tool_names"])
            .to_dicts()
        )

    async def _allowlist_image_ids(
        self,
        allowlist_species: set[str] | None,
    ) -> list[str] | None:
        if allowlist_species is None:
            return None
        return await asyncio.to_thread(
            self.image_meta_service.get_image_ids_for_species_list,
            sorted(allowlist_species),
            raise_on_error=True,
        )

    @staticmethod
    def _build_ranking_rows(
        dataframe: pl.DataFrame,
        *,
        tool_name: str,
    ) -> list[dict]:
        expected = {"imgId", "species", "distance"}
        if not expected.issubset(dataframe.columns):
            raise ValueError(
                f"Ranking result is missing columns: {expected - set(dataframe.columns)}"
            )

        # Vector search returns cosine distances (0 = identical, 2 = opposite).
        # Raw distances are not comparable across modalities: UNICOM
        # image-to-image matches land near 0.1-0.3 while CLIP text-to-image
        # matches land near 0.7-0.9, so scoring them as `1 - distance` reports a
        # genuine text match as near-zero confidence and clips everything at or
        # beyond 1.0 to a flat 0.0 that carries no ranking signal at all. Score
        # each candidate against the pool its own tool retrieved instead.
        distances = dataframe.get_column("distance").cast(pl.Float64)
        furthest = distances.max()
        nearest = distances.min()
        spread = (
            float(furthest) - float(nearest)
            if furthest is not None and nearest is not None
            else 0.0
        )
        if spread <= 0.0:
            score_expr = pl.lit(1.0, dtype=pl.Float64)
        else:
            closeness = (
                pl.lit(float(furthest)) - pl.col("distance").cast(pl.Float64)
            ) / spread
            score_expr = pl.lit(RANKING_SCORE_FLOOR) + closeness * (
                1.0 - RANKING_SCORE_FLOOR
            )

        return (
            dataframe.with_columns(
                score_expr.clip(0.0, 1.0).alias("score"),
                pl.lit(tool_name).alias("tool_names"),
            )
            .select(["imgId", "species", "score", "tool_names"])
            .to_dicts()
        )

    @staticmethod
    def _aggregate_ranking_results(
        rows: list[dict],
        *,
        filter_tool_names: list[str],
    ) -> pl.DataFrame:
        grouped: dict[str, dict[str, Any]] = {}
        filter_names = set(filter_tool_names)

        for row in rows:
            species = row["species"]
            score = float(row["score"])
            tool_name = row["tool_names"]
            item = grouped.setdefault(
                species,
                {
                    "imgId": row["imgId"],
                    "best_score": score,
                    "tool_scores": {},
                    "tools": set(filter_names),
                },
            )
            # Keep the strongest score per ranking tool so a tool returning
            # several rows for one species cannot inflate that species' mean.
            previous = item["tool_scores"].get(tool_name)
            if previous is None or score > previous:
                item["tool_scores"][tool_name] = score
            item["tools"].add(tool_name)
            if score > item["best_score"] or (
                score == item["best_score"] and str(row["imgId"]) < str(item["imgId"])
            ):
                item["imgId"] = row["imgId"]
                item["best_score"] = score

        results = [
            {
                "imgId": item["imgId"],
                "species": species,
                # Average only across the ranking tools that actually matched
                # this species. Dividing by every ranking tool that ran would
                # report a strong single-tool match as half-confidence.
                "score": min(
                    max(
                        sum(item["tool_scores"].values()) / len(item["tool_scores"]),
                        0.0,
                    ),
                    1.0,
                ),
                "tool_names": sorted(item["tools"]),
            }
            for species, item in grouped.items()
        ]
        results.sort(key=lambda row: (-row["score"], row["species"], row["imgId"]))
        return pl.DataFrame(results[:RESULT_LIMIT])

    @staticmethod
    def _build_filter_results(
        allowlist_species: set[str],
        executions: list[ToolExecution],
    ) -> pl.DataFrame:
        image_ids: dict[str, list[str]] = {species: [] for species in allowlist_species}
        tool_names = sorted(execution.call.name for execution in executions)

        for execution in executions:
            for row in execution.rows:
                if row["species"] in image_ids and row.get("imgId"):
                    image_ids[row["species"]].append(str(row["imgId"]))

        results = [
            {
                "imgId": min(ids),
                "species": species,
                "score": 1.0,
                "tool_names": tool_names,
            }
            for species, ids in image_ids.items()
            if ids
        ]
        results.sort(key=lambda row: (row["species"], row["imgId"]))
        return (
            pl.DataFrame(results[:RESULT_LIMIT])
            if results
            else AgentSearchService._empty_results()
        )

    @staticmethod
    def _normalize_species(value: str) -> str:
        return value.strip().lower().replace("_", " ")

    @staticmethod
    def _empty_results() -> pl.DataFrame:
        return pl.DataFrame(
            schema={
                "imgId": pl.String,
                "species": pl.String,
                "score": pl.Float64,
                "tool_names": pl.List(pl.String),
            }
        )
