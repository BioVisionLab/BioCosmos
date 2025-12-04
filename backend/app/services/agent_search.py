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


from typing import List, Dict, Any


from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel
from fastapi import Request
from openai import OpenAI


from ..services.image_meta import ImageMetaService
from ..configs.config import OpenAIConfig
from ..services.images import ImagePersistData
from ..services.gbif import GbifPersistData
from ..services.leptraits import LepTraits
from ..query.image_search import TextToImageSearch


logger = logging.getLogger(__name__)


class AgentSearchResult(BaseModel):
    """
    Represents a single species result from the agent search.

    Attributes:
        img_id: Image identifier - context-aware selection:
                - If color search used: Best matching image ID from color similarity
                - Otherwise: Main/representative image ID for the species
        species: Scientific name of the species (e.g., "Danaus plexippus")
        distance: Cosine distance for color similarity (0-2 range, lower is better).
                 Set to 0.0 if color search was not used.
        tool_calls: List of tool names that returned this species
                    (e.g., ["search_by_color", "search_by_location"])
        score: Computed ranking score (0-1 range, higher is better).
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


class AgentSearchPayload(BaseModel):
    """
    Complete search response payload containing ranked results.

    Attributes:
        query: Original user query string
        top_results: High-confidence results (score >= threshold, typically 0.3)
                     Sorted by score in descending order
        other_results: Lower-confidence results (score < threshold)
                       Sorted by score in descending order
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True
    )

    query: str
    top_results: List[AgentSearchResult]
    other_results: List[AgentSearchResult]


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
    Species are ranked using the weighted formula with dynamic normalization:
        Score = w_c * (1 - d_c/2) + w_l * m_l + w_t * m_t - penalty

    Where:
        - w_c, w_l, w_t: Configurable weights for color, location, traits
        - Weights are dynamically renormalized when color is not available
        - d_c: Cosine distance for color (0-2 range, normalized to 0-1)
        - m_l, m_t: Binary match indicators (1 if matched, 0 otherwise)
        - penalty: 0.15 * (num_tools_used - num_tools_for_species)

    Dynamic Weight Adjustment:
    --------------------------
    When color search is NOT used:
        - Color weight is excluded from calculation
        - Remaining weights are renormalized to sum to 1.0
        - Example: If only location and traits used, their weights become 0.5 each

    This ensures fair scoring regardless of which tools are invoked [web:33].

    The penalty ensures species found by multiple tools rank higher, improving precision.

    Image ID Selection:
    -------------------
    Image IDs are selected based on search context:
        - If color search used: Returns image ID with best color match (lowest distance)
        - Otherwise: Returns main/representative image ID for the species

    This ensures the most relevant image is displayed for each result.

    Example:
    --------
    Query: "Blue butterflies in Brazil"
    - LLM routes to: search_by_color("blue") AND search_by_location("Brazil")
    - Species found by both tools get higher scores than those from only one
    - Results sorted by final score
    """

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

        # Initialize data access services for different search modalities
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

        # Base ranking weights - controls relative importance of each search dimension
        # Updated to prioritize color when present
        self.weight_color = (
            0.5  # Increased priority for visual matches
        )
        self.weight_location = (
            0.25  # Weight for geographic occurrence
        )
        self.weight_traits = 0.25  # Weight for habitat/trait matching

    async def search(self, query: str) -> AgentSearchPayload:
        """
        Perform agent-based search on a natural language query.

        This is the main entry point for the search service. It:
        1. Sends the query to OpenAI with available tool definitions
        2. Executes all requested tools in parallel
        3. Aggregates results using weighted ranking with tool penalty
        4. Returns sorted results split into top/other categories

        The LLM is instructed to make a single decision about which tools to call,
        avoiding multi-turn conversations to minimize latency and token usage.

        Args:
            query: Natural language search query (e.g., "orange butterflies in Peru",
                   "species with high canopy affinity", "insects similar to Danaus plexippus")

        Returns:
            AgentSearchPayload containing:
                - query: Original query string
                - top_results: High-scoring species (score >= 0.3)
                - other_results: Lower-scoring species (score < 0.3)

            Both lists are sorted by score in descending order.

        Raises:
            Exception: If OpenAI API call fails or tool execution encounters errors
                      (logged but re-raised for upstream handling)

        Example:
            >>> service = AgentSearchService(request)
            >>> results = await service.search("blue butterflies in Costa Rica")
            >>> for result in results.top_results:
            ...     print(f"{result.species}: {result.score:.3f} (tools: {result.tool_calls})")
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
                    "6. SPECIFIC NAMES: Only use 'search_by_image_similarity' if the user specifically asks for species 'similar to' a scientific name. If they just say 'monarch', treat it as a visual/text search or map it to scientific name if needed, but prioritize attributes if present."
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]

        try:
            # Single call to LLM for tool selection - no multi-turn conversation
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let model decide which tools to use
                timeout=30.0,
            )

            message = response.choices[0].message

            # If no tools called, return empty results
            # This happens when query is unclear or outside biodiversity domain
            if not message.tool_calls:
                return AgentSearchPayload(
                    query=query, top_results=[], other_results=[]
                )

            # Execute all requested tools in parallel for performance
            tasks = []
            tool_names = []

            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(
                        tool_call.function.arguments
                    )
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse args for {function_name}"
                    )
                    continue

                tool_names.append(function_name)
                tasks.append(
                    self._execute_tool(function_name, function_args)
                )

            logger.info(
                f"Agent executing tools in parallel: {tool_names}"
            )

            # Await all tools - gather returns exceptions for failed tasks
            results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            # Process results and filter out errors
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Tool {tool_names[i]} failed: {result}"
                    )
                    continue
                if isinstance(result, dict) and "error" in result:
                    logger.error(
                        f"Tool {tool_names[i]} returned error: {result['error']}"
                    )
                    continue

                # Tag the result with the tool name for ranking metadata
                result["_tool_name"] = tool_names[i]
                valid_results.append(result)

            logger.info(
                f"Agent received {len(valid_results)}/{len(tool_names)} valid tool results"
            )

            final_results = self._aggregate_results(
                valid_results, query
            )
            return final_results.model_dump()

        except Exception as e:
            logger.error(f"Error in agent search: {e}", exc_info=True)
            raise

    def _aggregate_results(
        self, tool_results: List[Dict], query: str
    ) -> AgentSearchPayload:
        """
        Aggregate tool results using weighted ranking formula with dynamic normalization.

        Ranking Formula:
        ----------------
        Score = w_c * (1 - d_c/2) + w_l * m_l + w_t * m_t - penalty

        Where:
            w_c: Weight for color similarity (only if color search used)
            w_l: Weight for location match
            w_t: Weight for traits match
            d_c: Cosine distance for color [0, 2] - normalized to similarity [0, 1]
            m_l: Location match indicator (1 if found, 0 otherwise)
            m_t: Traits match indicator (1 if found, 0 otherwise)
            penalty: 0.15 * (num_tools_used - num_tools_for_species)

        Dynamic Weight Normalization:
        ------------------------------
        When color search is NOT invoked by the agent:
        - Color component is excluded from scoring
        - Remaining weights (location, traits) are renormalized to sum to 1.0
        - This ensures fair comparison regardless of which tools are used [web:33]

        Example:
        - Query with color: weights = {color: 0.5, location: 0.25, traits: 0.25}
        - Query without color: weights = {location: 0.5, traits: 0.5}

        Image ID Selection:
        -------------------
        Image IDs are selected based on search context:
        - If color search used AND species has color match: Use image ID with best color match
        - Otherwise: Use main/representative image ID for the species

        This ensures the most contextually relevant image is returned.

        The penalty ensures that:
        - Species found by all tools get no penalty
        - Species found by only 1 tool when 3 were used get -0.30 penalty
        - This heavily favors multi-tool matches, improving precision

        Args:
            tool_results: List of dictionaries from tool executions, each containing:
                         - "_tool_name": Name of the tool that produced the result
                         - "species_list": List of species (strings) or dicts with distance/img_id
            query: Original user query string (passed through to payload)

        Returns:
            AgentSearchPayload with:
                - top_results: Species with score >= 0.3 (configurable threshold)
                - other_results: Species with score < 0.3
                Both sorted by score descending

        Algorithm Details:
        ------------------
        1. Detect which tools were used to determine if color is available
        2. Build species_data dict tracking all occurrences of each species
        3. For color search: Store minimum cosine distance and corresponding image ID per species
        4. For other searches: Set binary match flags (location_match, traits_match)
        5. Dynamically renormalize weights if color not used
        6. Calculate weighted score with normalization
        7. Apply tool count penalty
        8. Select appropriate image ID based on whether color was used
        9. Sort and split by threshold
        """
        # Track species data across all tool results
        species_data: Dict[str, Dict[str, Any]] = {}

        num_tools_used = len(tool_results)

        # Detect if color search was used by checking tool names
        color_search_used = any(
            result.get("_tool_name") == "search_by_color"
            for result in tool_results
        )

        # First pass: Collect all species occurrences and their attributes
        for result in tool_results:
            tool_name = result.get("_tool_name", "unknown_tool")

            # Handle color search with cosine distances and image IDs
            # Color search returns list of {species, distance, img_id} dicts
            if tool_name == "search_by_color" and isinstance(
                result.get("species_list"), list
            ):
                for item in result["species_list"]:
                    species = item.get("species", "")
                    distance = item.get(
                        "distance", 1.0
                    )  # Default to max distance if missing
                    img_id = item.get(
                        "img_id", ""
                    )  # Image ID with this color match

                    if species not in species_data:
                        species_data[species] = {
                            "color_distance": None,
                            "color_img_id": None,  # Image ID from best color match
                            "location_match": 0,
                            "traits_match": 0,
                            "tools": set(),
                        }

                    # Store color distance and corresponding image ID (keep minimum distance)
                    if (
                        species_data[species]["color_distance"]
                        is None
                    ):
                        species_data[species]["color_distance"] = (
                            distance
                        )
                        species_data[species]["color_img_id"] = img_id
                    else:
                        # Keep minimum distance (best match) and its image ID
                        if (
                            distance
                            < species_data[species]["color_distance"]
                        ):
                            species_data[species][
                                "color_distance"
                            ] = distance
                            species_data[species]["color_img_id"] = (
                                img_id
                            )

                    species_data[species]["tools"].add(tool_name)

            # Handle other searches returning species lists (binary match)
            elif isinstance(result.get("species_list"), list):
                for species in result["species_list"]:
                    if species not in species_data:
                        species_data[species] = {
                            "color_distance": None,
                            "color_img_id": None,
                            "location_match": 0,
                            "traits_match": 0,
                            "tools": set(),
                        }

                    # Set appropriate binary match flag based on tool type
                    if tool_name == "search_by_location":
                        species_data[species]["location_match"] = 1
                    elif tool_name == "search_by_traits":
                        species_data[species]["traits_match"] = 1
                    elif tool_name == "search_by_image_similarity":
                        # Image similarity is treated as a trait match
                        # This is a design decision - could be adjusted
                        species_data[species]["traits_match"] = 1

                    species_data[species]["tools"].add(tool_name)

        # Dynamic weight normalization based on whether color search was used
        if color_search_used:
            # Use standard weights when color is available
            w_color = self.weight_color
            w_location = self.weight_location
            w_traits = self.weight_traits
            logger.debug(
                f"Using standard weights: color={w_color}, location={w_location}, traits={w_traits}"
            )
        else:
            # Renormalize weights excluding color to sum to 1.0
            # This ensures fair scoring when color is not available [web:33]
            w_color = 0.0
            total_weight = self.weight_location + self.weight_traits
            if total_weight > 0:
                w_location = self.weight_location / total_weight
                w_traits = self.weight_traits / total_weight
            else:
                # Fallback if both are zero (shouldn't happen with default config)
                w_location = 0.5
                w_traits = 0.5
            logger.debug(
                f"Color not used. Renormalized weights: location={w_location}, traits={w_traits}"
            )

        # Second pass: Calculate scores for each species and select appropriate image ID
        ranked_results = []

        for species, data in species_data.items():
            # Color component: Convert cosine distance [0,2] to similarity score [0,1]
            # Formula: similarity = 1 - (distance / 2)
            # This ensures:
            #   - distance=0 (identical) -> score=1.0
            #   - distance=1 (orthogonal) -> score=0.5
            #   - distance=2 (opposite) -> score=0.0
            # Only calculated if color search was used AND species has color data
            if (
                color_search_used
                and data["color_distance"] is not None
            ):
                color_score = 1 - (data["color_distance"] / 2.0)
            else:
                # No color contribution if color search not used or no color data for this species
                color_score = 0.0

            # Binary matches (either present or not)
            location_score = data["location_match"]  # 0 or 1
            traits_score = data["traits_match"]  # 0 or 1

            # Weighted linear combination with dynamically adjusted weights
            base_score = (
                w_color * color_score
                + w_location * location_score
                + w_traits * traits_score
            )

            # Penalty for using fewer tools
            # If query triggered 3 tools but species only appears in 1: penalty = 2 * 0.15 = 0.30
            # This strongly encourages multi-tool matches
            num_tools_for_species = len(data["tools"])
            tool_penalty = (
                num_tools_used - num_tools_for_species
            ) * 0.15

            # Final score, clamped to [0, 1] range
            final_score = max(0.0, base_score - tool_penalty)

            # Select appropriate image ID based on whether color search was used
            # Priority: color-matched image > main species image
            if color_search_used and data["color_img_id"]:
                # Use image ID from best color match
                img_id = data["color_img_id"]
            else:
                # Use main/representative image ID for the species
                img_id = (
                    self.image_meta_service.get_species_main_image_id(
                        species
                    )
                    or ""
                )

            ranked_results.append(
                AgentSearchResult(
                    img_id=img_id,
                    species=species,
                    tool_calls=list(data["tools"]),
                    score=final_score,
                )
            )

        # Sort by score descending (highest scores first)
        ranked_results.sort(key=lambda x: x.score, reverse=True)

        # Split into top and other results based on score threshold
        # Threshold of 0.3 means species must match at least one criterion well
        # or partially match multiple criteria
        threshold = 0.3
        top_results = [
            r for r in ranked_results if r.score >= threshold
        ]
        other_results = [
            r for r in ranked_results if r.score < threshold
        ]

        return AgentSearchPayload(
            query=query,
            top_results=top_results,
            other_results=other_results,
        )

    async def _execute_tool(
        self, function_name: str, function_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a specific tool function and standardize its output format.

        This method acts as a router to the appropriate search function based
        on the tool name. All tools return a dictionary with "species_list" key
        for consistent aggregation.

        Args:
            function_name: Name of the tool to execute (must match _get_tools() definitions)
            function_args: Dictionary of arguments parsed from LLM's tool call JSON

        Returns:
            Dictionary with standardized format:
                {
                    "species_list": [...],  # List of species strings or dicts
                    "_tool_name": str       # Added by caller for tracking
                }

            Or on error:
                {"error": "Error message"}

        Tool-specific return formats:
            - search_by_color: species_list contains dicts with {species, distance, img_id}
            - Other tools: species_list contains species name strings
        """
        if function_name == "search_by_image_similarity":
            species_list = await self._search_by_image_similarity(
                reference_species=function_args.get(
                    "reference_species"
                ),
                limit=function_args.get("limit", 400),
            )
            return {"species_list": species_list}

        elif function_name == "search_by_location":
            species_list = await self._search_by_location(
                location=function_args.get("location"),
                limit=function_args.get("limit", 400),
            )
            return {"species_list": species_list}

        elif function_name == "search_by_color":
            species_with_distances = await self._search_by_color(
                color_description=function_args.get(
                    "color_description"
                ),
                limit=function_args.get("limit", 50),
            )
            return {"species_list": species_with_distances}

        elif function_name == "search_by_traits":
            species_list = await self._search_by_traits(
                canopy_affinity=function_args.get("canopy_affinity"),
                edge_affinity=function_args.get("edge_affinity"),
                moisture_affinity=function_args.get(
                    "moisture_affinity"
                ),
                disturbance_affinity=function_args.get(
                    "disturbance_affinity"
                ),
                limit=function_args.get("limit", 400),
            )
            return {"species_list": species_list}

        else:
            return {"error": f"Unknown function: {function_name}"}

    async def _search_by_image_similarity(
        self, reference_species: str, limit: int = 50
    ) -> List[str]:
        """
        Find species visually similar to a reference species using image embeddings.

        This search:
        1. Retrieves all image IDs for the reference species
        2. Queries the vector database for similar images (using cosine similarity)
        3. Returns unique species names from similar images

        Use case: "Find butterflies that look like Danaus plexippus"

        Args:
            reference_species: Scientific name of the reference species
                              (e.g., "Danaus plexippus")
            limit: Maximum number of similar images to retrieve (default 50)

        Returns:
            List of unique species names (scientific names) found in similar images.
            Empty list if reference species has no images or no similar images found.

        Note:
            This returns species names only (no distance scores or image IDs) because the
            image similarity distance is between images, not species. A species
            may have multiple images at different distances, making aggregation complex.
            For image selection, main species image is used via get_species_main_image_id.
        """
        scientific_name = (reference_species or "").strip()

        # Get all image IDs for the reference species
        image_ids = self.image_meta_service.get_image_ids_by_species(
            scientific_name
        )

        # Pass IDs to find visual lookalikes using vector similarity
        similar_images = self.image_service.find_similar_images(
            image_ids=image_ids, limit=limit
        )

        # Convert Polars DataFrame to dicts if necessary
        if similar_images is not None and hasattr(
            similar_images, "to_dicts"
        ):
            similar_images = similar_images.to_dicts()

        if not similar_images:
            return []

        # Extract unique species names, converting underscores to spaces
        species_names = [
            item.get("species", "").replace("_", " ")
            for item in similar_images
            if item.get("species")
        ]

        # Return unique species names (set removes duplicates)
        return list(set(species_names))

    async def _search_by_location(
        self, location: str, limit: int = 100
    ) -> List[str]:
        """
        Search for species occurring in a specific geographic location.

        This queries the GBIF (Global Biodiversity Information Facility) occurrence
        database for species recorded in the specified location.

        Use case: "Find all butterflies in Costa Rica"

        Args:
            location: Geographic location (country name, region, or broader area)
                     Examples: "Brazil", "Costa Rica", "Amazon"
                     The GBIF service handles location standardization
            limit: Maximum number of species to return (default 100)

        Returns:
            List of species names (scientific names) found in the location.
            Empty list if location not found or no species recorded.

        Note:
            Location matching depends on GBIF data quality and coverage.
            Some regions may have better data than others.
            For image selection, main species image is used via get_species_main_image_id.
        """
        species_names = self.gbif_service.search_by_location(
            location=location, limit=limit
        )
        return species_names or []

    async def _search_by_color(
        self, color_description: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for species matching a color description using CLIP embeddings.

        This search:
        1. Converts color description to CLIP text embedding
        2. Queries image database using cosine similarity
        3. Aggregates results by species, keeping minimum distance and corresponding image ID
        4. Returns species with their best (lowest) distance scores and matching image IDs

        Use case: "Find blue butterflies", "orange spots", "iridescent wings"

        Args:
            color_description: Natural language color description
                              Examples: "blue", "orange and black", "metallic green"
            limit: Target number of species to return (default 50)
                  Note: Searches 10x images (min 3000) to ensure diversity,
                  then aggregates to species level

        Returns:
            List of dictionaries, each containing:
                {
                    "species": str,    # Scientific name
                    "distance": float, # Cosine distance [0-2], lower is better
                    "img_id": str      # Image ID with best color match
                }
            Sorted by distance (best matches first).
            Empty list if no matches found.

        Implementation Details:
        -----------------------
        - Uses CLIP (Contrastive Language-Image Pre-training) embeddings
        - Cosine distance range: [0, 2]
          * 0 = identical vectors
          * 1 = orthogonal (90 degrees)
          * 2 = opposite directions (180 degrees)
        - Aggregates by species using minimum distance (best match per species)
        - Stores image ID corresponding to best match for each species
        - Over-fetches images to ensure species diversity after aggregation
        """
        # Over-fetch images to ensure diversity after species-level aggregation
        image_limit = max(limit * 10, 3000)

        text_search = TextToImageSearch(
            request=self.request,
            query=color_description,
            limit=image_limit,
        )
        results = text_search.search()

        if not results:
            return []

        # Aggregate by species, keeping minimum (best) distance and corresponding image ID
        species_data: Dict[str, Dict[str, Any]] = {}

        for item in results:
            species = item.get("species", "").replace("_", " ")
            distance = item.get(
                "distance", 1.0
            )  # Default to median distance
            img_id = item.get("img_id", "")  # Image ID for this match

            if species:
                if species not in species_data:
                    species_data[species] = {
                        "distance": distance,
                        "img_id": img_id,
                    }
                else:
                    # Keep minimum distance (best match) and its image ID
                    if distance < species_data[species]["distance"]:
                        species_data[species]["distance"] = distance
                        species_data[species]["img_id"] = img_id

        # Convert to list of dicts for consistent return format
        return [
            {
                "species": species,
                "distance": data["distance"],
                "img_id": data["img_id"],
            }
            for species, data in species_data.items()
        ]

    async def _search_by_traits(
        self,
        canopy_affinity=None,
        edge_affinity=None,
        moisture_affinity=None,
        disturbance_affinity=None,
        limit=100,
    ) -> List[str]:
        """
        Search species by habitat preferences and ecological traits.

        This queries the LepTraits database for species matching ALL specified
        trait criteria (AND logic). Each trait represents the species' affinity
        for a particular habitat characteristic.

        Use case: "Find species that prefer high canopy and low disturbance"

        Args:
            canopy_affinity: Preference for canopy cover ("High", "Medium", "Low", or None)
                           High = prefers dense canopy, Low = prefers open areas
            edge_affinity: Preference for habitat edges ("High", "Medium", "Low", or None)
                          High = edge specialist, Low = interior specialist
            moisture_affinity: Preference for moisture ("High", "Medium", "Low", or None)
                             High = wet habitats, Low = dry habitats
            disturbance_affinity: Tolerance of disturbance ("High", "Medium", "Low", or None)
                                High = disturbance-tolerant, Low = disturbance-sensitive
            limit: Maximum number of species to return (default 100)

        Returns:
            List of species names (scientific names) matching ALL specified traits.
            Empty list if no traits specified or no matches found.

        Query Logic:
        ------------
        - Only non-None parameters are included in the query
        - Multiple conditions are combined with AND (intersection)
        - Example: canopy="High" AND moisture="Low" returns only species
          that prefer both high canopy AND low moisture

        Database Schema:
        ----------------
        The LepTraits table contains columns:
        - Species: Scientific name
        - CanopyAffinity: High/Medium/Low
        - EdgeAffinity: High/Medium/Low
        - MoistureAffinity: High/Medium/Low
        - DisturbanceAffinity: High/Medium/Low

        Note:
            Currently limited to Lepidoptera (butterflies/moths).
            Trait data quality varies by species.
            For image selection, main species image is used via get_species_main_image_id.
        """
        conditions = []

        # Build WHERE clause conditions for non-None parameters
        if canopy_affinity:
            conditions.append(f"CanopyAffinity = '{canopy_affinity}'")
        if edge_affinity:
            conditions.append(f"EdgeAffinity = '{edge_affinity}'")
        if moisture_affinity:
            conditions.append(
                f"MoistureAffinity = '{moisture_affinity}'"
            )
        if disturbance_affinity:
            conditions.append(
                f"DisturbanceAffinity = '{disturbance_affinity}'"
            )

        # Return empty if no traits specified
        if not conditions:
            return []

        # Build SQL query with AND conditions
        where_clause = " AND ".join(conditions)
        query = f"SELECT DISTINCT Species FROM {self.leptraits_service.table} WHERE {where_clause} LIMIT {limit}"

        # Execute query and return species list
        result = self.leptraits_service.db_client.execute(query).pl()
        return (
            result["Species"].to_list()
            if not result.is_empty()
            else []
        )

    def _get_tools(self) -> List[Dict]:
        """
        Define available tools for OpenAI function calling.

        These tool definitions are sent to the LLM, which decides which tools
        to call based on the user query. Each tool definition includes:
        - Name: Unique identifier for the function
        - Description: Helps LLM understand when to use the tool
        - Parameters: JSON Schema defining required and optional arguments

        Returns:
            List of tool definitions in OpenAI function calling format.

        Tool Descriptions:
        ------------------
        1. search_by_image_similarity: Visual similarity search
           - Finds species that look like a reference species
           - Useful for "similar to X" queries

        2. search_by_location: Geographic occurrence search
           - Finds species in a specific country/region
           - Useful for "in Location" queries

        3. search_by_color: Color-based image search
           - Finds species matching color descriptions
           - Useful for color/pattern queries
           - Returns cosine distances and image IDs for ranking and display

        4. search_by_traits: Ecological trait filtering
           - Finds species by habitat preferences
           - Useful for trait/habitat queries

        Design Principles:
        ------------------
        - Descriptions are concise but informative to minimize token usage
        - Examples in descriptions guide LLM to correct tool usage
        - Default limits are set high to maximize recall, refined in aggregation
        - Enum constraints prevent invalid trait values
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_by_image_similarity",
                    "description": (
                        "Finds species visually similar to a specific scientific name. "
                        "Use when user asks for species that look like, resemble, or are "
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
                        "Use when user specifies a location constraint. "
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
                        "Use when user describes colors, patterns, or visual appearance. "
                        "Returns cosine distances and image IDs for ranking and display. "
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
                        "Use when user specifies habitat characteristics or ecological traits. "
                        "Example: 'species with high canopy affinity', 'disturbance-tolerant butterflies'"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "canopy_affinity": {
                                "type": "string",
                                "enum": [
                                    "High",
                                    "Medium",
                                    "Low",
                                    None,
                                ],
                                "description": (
                                    "Preference for canopy cover. "
                                    "High = dense canopy, Low = open areas"
                                ),
                            },
                            "edge_affinity": {
                                "type": "string",
                                "enum": [
                                    "High",
                                    "Medium",
                                    "Low",
                                    None,
                                ],
                                "description": (
                                    "Preference for habitat edges. "
                                    "High = edge specialist, Low = interior specialist"
                                ),
                            },
                            "moisture_affinity": {
                                "type": "string",
                                "enum": [
                                    "High",
                                    "Medium",
                                    "Low",
                                    None,
                                ],
                                "description": (
                                    "Preference for moisture. "
                                    "High = wet habitats, Low = dry habitats"
                                ),
                            },
                            "disturbance_affinity": {
                                "type": "string",
                                "enum": [
                                    "High",
                                    "Medium",
                                    "Low",
                                    None,
                                ],
                                "description": (
                                    "Tolerance of habitat disturbance. "
                                    "High = disturbance-tolerant, Low = disturbance-sensitive"
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Maximum number of species to return",
                            },
                        },
                        # Note: No required parameters - user can specify any combination
                    },
                },
            },
        ]
