"""Agent-based semantic search orchestration for biodiversity data."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import polars as pl
from fastapi import Request
from openai import APITimeoutError, AuthenticationError, OpenAI, PermissionDeniedError
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..configs.config import OpenAIConfig, PromptsConfig
from ..query.locality_species import LocalitySpecies
from .agent_tools import (
    AgentWarning,
    ColorArgs,
    CommonNameArgs,
    ImageSimilarityArgs,
    LocationArgs,
    ParsedToolCall,
    TraitArgs,
    build_tool_definitions,
    build_tool_registry,
    parse_tool_calls,
)
from .common_names import CommonNameSearch
from .gbif import GbifPersistData
from .images import ImagePersistData
from .leptraits import LepTraits
from .metadata import ImageMetaService
from .species_pages import SpeciesPageResolver, attach_page_keys

logger = logging.getLogger(__name__)

# Results are served a page at a time; the ranked list behind them is kept
# (up to MAX_RANKED_RESULTS) so "show more" never re-runs the planner.
PAGE_SIZE = 35
MAX_RANKED_RESULTS = 500
VECTOR_CANDIDATE_LIMIT = 500
FILTER_SPECIES_LIMIT = 10_000
PLANNER_MAX_TOKENS = 512
PLANNER_TIMEOUT_SECONDS = 30.0
# Every ranked candidate already cleared the vector-search cutoff, so the
# weakest one in a pool is still a match and must not be reported as 0%.
RANKING_SCORE_FLOOR = 0.5


# Trait argument -> the recorded LepTraits categories it stands for. The
# habitat affinities are graded ("strong", "weak"); both grades count.
_TRAIT_CATEGORIES: dict[str, tuple[str, dict[str, tuple[str, ...]]]] = {
    "canopy": (
        "canopy_affinity",
        {
            "closed": (
                "Closed canopy",
                "Closed canopy (+edge)",
                "Mixed canopy (closed affinity)",
            ),
            "open": (
                "Open canopy",
                "Semi-open canopy",
                "Mixed canopy (open affinity)",
            ),
            "mixed": (
                "Mixed canopy",
                "Mixed canopy (open affinity)",
                "Mixed canopy (closed affinity)",
            ),
            "generalist": ("Canopy generalist",),
            "edge": ("Edge associated", "Closed canopy (+edge)"),
        },
    ),
    "edge": (
        "edge_affinity",
        {
            "associated": ("Edge-associated (strong)", "Edge-associated (weak)"),
            "avoidant": ("Edge-avoidant (strong)", "Edge-avoidant (weak)"),
        },
    ),
    "moisture": (
        "moisture_affinity",
        {
            "wet": ("Mesic-associated (strong)", "Mesic-associated (weak)"),
            "dry": ("Xeric-associated (strong)", "Xeric-associated (weak)"),
        },
    ),
    "disturbance": (
        "disturbance_affinity",
        {
            "tolerant": (
                "Disturbance-associated (strong)",
                "Disturbance-associated (weak)",
            ),
            "avoidant": (
                "Disturbance-avoidant (strong)",
                "Disturbance-avoidant (weak)",
            ),
        },
    ),
    "voltinism": (
        "voltinism",
        {
            "univoltine": ("Univoltine",),
            "bivoltine": ("Bivoltine",),
            "multivoltine": ("Multivoltine",),
        },
    ),
    "host_breadth": (
        "host_breadth",
        {"specialist": ("Specialist",), "generalist": ("Generalist",)},
    ),
    "wing_size": (
        "wing_size",
        {"small": ("Small",), "medium": ("Medium",), "large": ("Large",)},
    ),
}

# Trait argument -> index column holding a comma-separated list of words.
_TRAIT_LISTS = {
    "diapause_stage": "diapause_stage",
    "oviposition": "oviposition_style",
    "hostplant_family": "hostplant_families",
    "flight_months": "flight_months",
}


def trait_predicate(field_name: str, value: Any) -> tuple[str, list[Any]]:
    """A WHERE fragment over the trait index for one validated argument.

    Column names come from the tables above, never from the request; the
    values are bound. Several flight months match a species flying in any.
    """
    if field_name in _TRAIT_CATEGORIES:
        column, categories = _TRAIT_CATEGORIES[field_name]
        recorded = categories[value]
        placeholders = ", ".join("?" for _ in recorded)
        return f"t.{column} IN ({placeholders})", list(recorded)
    if field_name in _TRAIT_LISTS:
        column = _TRAIT_LISTS[field_name]
        words = value if isinstance(value, list) else [value]
        matches = " OR ".join(
            f"list_contains(string_split(lower(t.{column}), ', '), ?)" for _ in words
        )
        return f"({matches})", [str(word).lower() for word in words]
    raise ValueError(f"Unsupported trait argument: {field_name}")


class AgentSearchResult(BaseModel):
    """Public result item returned by agent search."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    img_id: str
    species: str
    # The species page the result links to; see `species_pages`. Absent from
    # results cached before it existed.
    species_key: str | None = None
    tool_names: list[str] = Field(default_factory=list, alias="tool_names")


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
        locality_species: LocalitySpecies | None = None,
        species_pages: SpeciesPageResolver | None = None,
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
        self.common_name_search = CommonNameSearch(duckdb)
        self.gbif_service = gbif_service or GbifPersistData(duckdb=duckdb)
        self.leptraits_service = leptraits_service or LepTraits(duckdb=duckdb)
        self.locality_species = locality_species or LocalitySpecies(duckdb)
        self.species_pages = species_pages or SpeciesPageResolver(duckdb)

    async def search(self, query: str) -> AgentSearchOutcome:
        """Run a single planner request followed by filter-first tool execution.

        Every result links to a valid species page. The tools work on recorded
        names, so the final list is resolved once here: a result with no page
        is dropped, and two spellings of one species keep the higher-ranked.
        """
        outcome = await self._search(query)
        dataframe = await asyncio.to_thread(self._link_species_pages, outcome.dataframe)
        return AgentSearchOutcome(dataframe, outcome.warnings)

    def _link_species_pages(self, dataframe: pl.DataFrame) -> pl.DataFrame:
        if dataframe.is_empty():
            return dataframe.with_columns(pl.lit(None, pl.String).alias("speciesKey"))
        keyed = attach_page_keys(dataframe, self.species_pages)
        # Rows arrive ranked, so the first of each page is the one to keep.
        # Records the fallback could not key (genus-only) stay, unlinked. A
        # result names the species of the page it links to, not whichever
        # recorded variant (a misspelling, a trinomial) its image was filed as.
        return keyed.with_columns(
            pl.coalesce(pl.col("speciesKey"), pl.col("species")).alias("species")
        ).unique(subset=["species"], keep="first", maintain_order=True)

    async def _search(self, query: str) -> AgentSearchOutcome:
        response = await self._plan(query)
        if not getattr(response, "choices", None):
            raise AgentPlannerError("The planner returned no choices.")

        message = response.choices[0].message
        raw_tool_calls = list(getattr(message, "tool_calls", None) or [])
        calls, warnings = parse_tool_calls(raw_tool_calls, self.tool_registry)
        if not calls:
            # A small planner model sometimes answers a purely descriptive
            # query ("owl-like butterfly") with no tool at all. The raw query
            # is still a usable CLIP prompt, so rank by it instead of
            # returning nothing.
            logger.info("Planner selected no usable tools; using text search.")
            calls = [self._text_search_fallback(query)]

        filter_calls = [call for call in calls if call.category == "filter"]
        ranking_calls = [call for call in calls if call.category == "ranking"]

        # Tools within a stage are independent, so run them concurrently.
        filter_executions = list(
            await asyncio.gather(
                *(
                    self._execute_safely(call, allowlist_species=None)
                    for call in filter_calls
                )
            )
        )
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

        ranking_executions = list(
            await asyncio.gather(
                *(
                    self._execute_safely(call, allowlist_species)
                    for call in ranking_calls
                )
            )
        )
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

    def _text_search_fallback(self, query: str) -> ParsedToolCall:
        spec = self.tool_registry["search_by_color"]
        return ParsedToolCall(
            name=spec.name,
            category=spec.category,
            args=ColorArgs(color_description=query[:200]),
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
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise AgentConfigurationError(
                "The planner provider denied access to the configured model."
            ) from exc
        except APITimeoutError as exc:
            logger.exception("Planner request timed out.")
            raise AgentPlannerTimeoutError("The planner request timed out.") from exc
        except Exception as exc:
            logger.exception("Planner request failed.")
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
            logger.exception("Tool '%s' failed.", call.name)
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
        if isinstance(call.args, CommonNameArgs):
            species = await asyncio.to_thread(
                self.common_name_search.search, call.args.common_name
            )
            return await self._species_to_filter_rows(
                species, tool_name="search_by_common_name"
            )
        if isinstance(call.args, ImageSimilarityArgs):
            return await self._search_by_image_similarity(
                call.args.reference_species,
                allowlist_species,
            )
        if isinstance(call.args, LocationArgs):
            return await self._search_by_location(
                call.args.normalized_country(),
                call.args.state_province,
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
        excluded_species: str | list[str] | None = reference_species
        if not image_ids:
            references = await asyncio.to_thread(
                self.common_name_search.search, reference_species
            )
            if references:
                reference_ids = await asyncio.gather(
                    *(
                        asyncio.to_thread(
                            self.image_meta_service.get_image_ids_by_species,
                            species,
                            raise_on_error=True,
                        )
                        for species in references
                    )
                )
                image_ids = sorted(
                    {image_id for ids in reference_ids for image_id in ids}
                )
                excluded_species = references
        if not image_ids and len(reference_species.split()) == 1:
            # Preserve explicit genus references and their existing behavior:
            # use the genus's images while keeping its species in the results.
            image_ids = await asyncio.to_thread(
                self.image_meta_service.get_image_ids_by_genus,
                reference_species,
                raise_on_error=True,
            )
            excluded_species = None
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
            exclude_species=excluded_species,
            min_species=PAGE_SIZE,
            raise_on_error=True,
        )
        if similar is None or similar.is_empty():
            return []
        return self._build_ranking_rows(
            similar,
            tool_name="search_by_image_similarity",
        )

    async def _search_by_location(
        self, country: str, state_province: str | None = None
    ) -> list[dict]:
        if await asyncio.to_thread(self.locality_species.available):
            species_names = await asyncio.to_thread(
                self.locality_species.species,
                country,
                state_province,
                FILTER_SPECIES_LIMIT,
            )
        else:
            # Without the locality table there is no ADM1 to match against, so
            # the filter can only be as narrow as the recorded country.
            if state_province:
                logger.warning(
                    "Locality table unavailable; ignoring state_province %r.",
                    state_province,
                )
            species_names = await asyncio.to_thread(
                self.gbif_service.search_by_country_code,
                country,
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
        """Every recorded name of the species whose traits match.

        The trait index keys LepTraits to occurrences through their accepted
        species, so this returns each spelling the collection files a matching
        species under. That is what lets the result intersect with the other
        filters and allowlist images, both of which work on recorded names.
        """
        db_client = self.leptraits_service.db_client
        traits_table = self.leptraits_service.index_table
        if not await asyncio.to_thread(db_client.table_exists, traits_table):
            # An empty result would read as "no species has these traits" and
            # empty the whole search; failing reports the constraint instead.
            raise RuntimeError(f"The trait index '{traits_table}' has not been built.")

        conditions: list[str] = []
        params: list[Any] = []
        for field_name, value in args.model_dump(exclude_none=True).items():
            condition, condition_params = trait_predicate(field_name, value)
            conditions.append(condition)
            params.extend(condition_params)

        sql = (
            f"SELECT DISTINCT o.species FROM {self.image_meta_service.table} o "
            f"JOIN {traits_table} t USING (img_id) "
            f"WHERE {' AND '.join(conditions)} ORDER BY o.species LIMIT ?"
        )
        params.append(FILTER_SPECIES_LIMIT)
        result = await asyncio.to_thread(db_client.execute_prepared_to_pl, sql, params)
        species_names = result["species"].to_list() if not result.is_empty() else []
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
            self.image_meta_service.get_species_first_image_ids,
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
        return pl.DataFrame(results[:MAX_RANKED_RESULTS])

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
            pl.DataFrame(results[:MAX_RANKED_RESULTS])
            if results
            else AgentSearchService._empty_results()
        )

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
