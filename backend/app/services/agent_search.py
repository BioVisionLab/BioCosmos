"""
Agent-based semantic search service.
Uses OpenAI function calling to intelligently query multiple data sources.
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional

from fastapi import Request
from openai import OpenAI

from ..configs.config import OpenAIConfig
from ..services.images import ImagePersistData
from ..services.gbif import GbifPersistData
from ..services.leptraits import LepTraits
from ..query.image_search import TextToImageSearch, ImageToImageSearch  # kept for compatibility

logger = logging.getLogger(__name__)


class AgentSearchService:
    """
    Agent-based search service that uses OpenAI function calling
    to intelligently query multiple data sources.
    """

    def __init__(self, request: Request):
        self.request = request
        config = OpenAIConfig()
        if not config.api_key or not config.api_url:
            raise ValueError("OpenAI API key and URL must be configured for agent search")
        self.client = OpenAI(
            base_url=config.api_url,
            api_key=config.api_key,
        )
        self.model = config.model or "gpt-4o"

        # Initialize data access services
        self.image_service = ImagePersistData(
            lance_db=request.app.state.lance_db
        )
        self.gbif_service = GbifPersistData(
            duckdb=request.app.state.duck_db
        )
        self.leptraits_service = LepTraits(
            duckdb=request.app.state.duck_db
        )

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Perform agent-based search on a natural language query.

        Args:
            query: Natural language search query

        Returns:
            List of species results matching the query
        """
        tools = self._get_tools()

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert biodiversity search assistant. "
                    "Your job is to help users find butterfly species by intelligently "
                    "querying multiple data sources including image similarity, "
                    "geographic location, morphological traits, and habitat preferences. "
                    "When the user uses common species names (e.g., 'monarch'), "
                    "you MUST infer the corresponding canonical scientific name "
                    "(e.g., 'Danaus plexippus') before calling tools. "
                    "For geographic queries, pass country or region names "
                    "that match how they appear in biodiversity databases "
                    "(e.g., 'Ecuador', 'Brazil', 'South America'). "
                    "Break down complex queries into multiple tool calls and combine results. "
                    "When combining results from multiple tools, find species that match ALL criteria."
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let the model decide which tools to use
                temperature=0.1,      # More deterministic tool selection
                timeout=60.0,
            )

            message = response.choices[0].message

            # If the model wants to call tools, execute them
            if message.tool_calls:
                tool_results = []
                full_results = []  # Store full results for final response
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    logger.info(f"Agent calling tool: {function_name} with args: {function_args}")
                    result = await self._execute_tool(function_name, function_args)
                    # Store full result with tool name for proper parsing
                    full_results.append({
                        "name": function_name,
                        "result": result
                    })
                    # Summarize result to reduce token usage (truncate large species lists)
                    summarized_result = self._summarize_tool_result(result) if isinstance(result, dict) else result
                    tool_results.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(summarized_result) if isinstance(summarized_result, (dict, list)) else str(summarized_result),
                        }
                    )

                # Add tool results to conversation
                messages.append(message)
                messages.extend(tool_results)

                # Get final response from the model
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=0.1,
                    timeout=60.0,
                )

                final_message = final_response.choices[0].message

                # If the model makes more tool calls, continue the conversation
                if final_message.tool_calls:
                    return await self._handle_tool_calls(final_message, messages, tools, full_results=full_results)

                # Otherwise, parse the response for results using FULL results
                return self._parse_results(final_message.content or "", full_results)

            # No tool calls, return direct response
            return self._parse_direct_response(message.content or "")

        except Exception as e:
            logger.error(f"Error in agent search: {e}", exc_info=True)
            raise

    async def _handle_tool_calls(
        self,
        message,
        messages: List[Dict],
        tools: List[Dict],
        max_iterations: int = 5,
        full_results: List[Dict] | None = None,
    ) -> List[Dict[str, Any]]:
        """Recursively handle tool calls up to max_iterations."""
        if max_iterations <= 0:
            logger.warning("Max tool call iterations reached")
            return []

        if full_results is None:
            full_results = []

        tool_results = []
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            logger.info(f"Agent calling tool (iteration): {function_name} with args: {function_args}")
            result = await self._execute_tool(function_name, function_args)
            # Store full result with tool name for proper parsing
            full_results.append({
                "name": function_name,
                "result": result
            })
            # Summarize result to reduce token usage (truncate large species lists)
            summarized_result = self._summarize_tool_result(result) if isinstance(result, dict) else result
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(summarized_result) if isinstance(summarized_result, (dict, list)) else str(summarized_result),
                }
            )

        messages.append(message)
        messages.extend(tool_results)

        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            temperature=0.1,
            timeout=60.0,
        )

        final_message = final_response.choices[0].message

        if final_message.tool_calls:
            return await self._handle_tool_calls(final_message, messages, tools, max_iterations - 1, full_results=full_results)

        return self._parse_results(final_message.content or "", full_results)

    def _summarize_tool_result(self, result: Dict[str, Any], max_species: int = 50) -> Dict[str, Any]:
        """
        Summarize tool results to reduce token usage when sending to OpenAI.
        Keeps counts and metadata but truncates large species lists.
        
        Args:
            result: The full tool result dictionary
            max_species: Maximum number of species to include in summary
            
        Returns:
            Summarized result with truncated species lists
        """
        if not isinstance(result, dict):
            return result
        
        summary = result.copy()
        
        # Truncate species lists if they're too long
        if "species" in summary and isinstance(summary["species"], list):
            species_list = summary["species"]
            if len(species_list) > max_species:
                summary["species"] = species_list[:max_species]
                summary["_truncated"] = True
                summary["_total_count"] = len(species_list)
                summary["_message"] = (
                    f"Showing first {max_species} of {len(species_list)} species. "
                    f"Full list available in final results."
                )
        
        # Remove large similarity_scores arrays (keep only count if needed)
        if "similarity_scores" in summary and isinstance(summary["similarity_scores"], list):
            if len(summary["similarity_scores"]) > 20:
                summary["similarity_scores"] = summary["similarity_scores"][:20]
                summary["_similarity_scores_truncated"] = True
        
        return summary

    def _get_tools(self) -> List[Dict]:
        """Define available tools for the agent."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_by_image_similarity",
                    "description": (
                        "Search for butterfly species that look visually similar to a given species. "
                        "ALWAYS pass the canonical scientific name used in biodiversity databases "
                        "(e.g., 'Danaus plexippus' for monarch, 'Morpho menelaus' for blue morpho). "
                        "If the user mentions a common name, first infer the corresponding "
                        "scientific name and pass that as the argument."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reference_species": {
                                "type": "string",
                                "description": (
                                    "The scientific name of the reference butterfly species. "
                                    "Examples: 'Danaus plexippus', 'Morpho menelaus', "
                                    "'Vanessa cardui'. Do NOT pass common names here."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 50)",
                                "default": 50,
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
                        "Search for butterfly species found in a specific geographic location. "
                        "Pass the country, region, or continent name as it appears in biodiversity "
                        "data (e.g., 'Ecuador', 'Brazil', 'South America'). "
                        "If the user uses colloquial or vague region names (e.g., 'the Amazon'), "
                        "infer the most appropriate country or region name to use."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": (
                                    "Geographic location name (country, region, or continent). "
                                    "Examples: 'Ecuador', 'Brazil', 'South America'."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 100)",
                                "default": 500,
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
                        "Search for butterfly species with specific color characteristics. "
                        "Use this when the query mentions colors (e.g., 'red', 'blue', 'orange', 'black and white'). "
                        "This tool uses text-to-image embeddings over specimen images."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "color_description": {
                                "type": "string",
                                "description": (
                                    "Description of color(s) to search for "
                                    "(e.g., 'red', 'orange and black', 'blue dorsal wings')."
                                ),
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 50)",
                                "default": 150,
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
                        "Search for butterfly species by ecological traits and habitat preferences. "
                        "Use this when the query mentions habitat types (e.g., 'canopy', 'edge', 'forest'), "
                        "moisture preferences, disturbance tolerance, or other ecological traits."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "canopy_affinity": {
                                "type": "string",
                                "description": "Canopy habitat preference: 'High', 'Medium', 'Low', or None",
                                "enum": ["High", "Medium", "Low", None],
                            },
                            "edge_affinity": {
                                "type": "string",
                                "description": "Edge habitat preference: 'High', 'Medium', 'Low', or None",
                                "enum": ["High", "Medium", "Low", None],
                            },
                            "moisture_affinity": {
                                "type": "string",
                                "description": "Moisture preference: 'High', 'Medium', 'Low', or None",
                                "enum": ["High", "Medium", "Low", None],
                            },
                            "disturbance_affinity": {
                                "type": "string",
                                "description": "Disturbance tolerance: 'High', 'Medium', 'Low', or None",
                                "enum": ["High", "Medium", "Low", None],
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 100)",
                                "default": 100,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "combine_search_results",
                    "description": (
                        "Combine results from multiple search tools to find species that match ALL criteria. "
                        "Use this after calling multiple search functions to find the intersection of results."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "species_lists": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "description": "List of species name lists from different search tools",
                            }
                        },
                        "required": ["species_lists"],
                    },
                },
            },
        ]

    async def _execute_tool(self, function_name: str, function_args: Dict[str, Any]) -> Any:
        """Execute a tool function and return results."""
        try:
            if function_name == "search_by_image_similarity":
                return await self._search_by_image_similarity(
                    reference_species=function_args.get("reference_species"),
                    limit=function_args.get("limit", 400),
                )

            elif function_name == "search_by_location":
                return await self._search_by_location(
                    location=function_args.get("location"),
                    limit=function_args.get("limit", 400),
                )

            elif function_name == "search_by_color":
                return await self._search_by_color(
                    color_description=function_args.get("color_description"),
                    limit=function_args.get("limit", 50),
                )

            elif function_name == "search_by_traits":
                return await self._search_by_traits(
                    canopy_affinity=function_args.get("canopy_affinity"),
                    edge_affinity=function_args.get("edge_affinity"),
                    moisture_affinity=function_args.get("moisture_affinity"),
                    disturbance_affinity=function_args.get("disturbance_affinity"),
                    limit=function_args.get("limit", 400),
                )

            elif function_name == "combine_search_results":
                return self._combine_search_results(
                    species_lists=function_args.get("species_lists", []),
                )

            else:
                logger.warning(f"Unknown tool function: {function_name}")
                return {"error": f"Unknown function: {function_name}"}

        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}", exc_info=True)
            return {"error": str(e)}

    async def _search_by_image_similarity(
        self,
        reference_species: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search for species similar to a reference species using image embeddings."""
        try:
            # At this point, the LLM is expected to have passed a canonical scientific name
            scientific_name = (reference_species or "").strip()
            logger.info(f"Using '{scientific_name}' for image similarity search")

            similar_species = self.image_service.fetch_id_similar_images(
                species_name=scientific_name,
                limit=limit,
            )

            if not similar_species:
                logger.warning(
                    f"No similar species found for {scientific_name} "
                    f"(original argument: {reference_species})"
                )
                species_exists = False
                try:
                    test_query = self.image_service._query_image(scientific_name)
                    if test_query is not None and len(test_query) > 0:
                        species_exists = True
                        logger.info(
                            f"Species {scientific_name} exists in database "
                            f"but has no similar species"
                        )
                except Exception as check_error:
                    logger.debug(f"Error checking if species exists: {check_error}")
                    species_exists = False

                if not species_exists:
                    return {
                        "species": [],
                        "count": 0,
                        "message": (
                            f"Reference species '{reference_species}' "
                            f"(scientific name argument: '{scientific_name}') "
                            f"not found in database."
                        ),
                        "tried_scientific_name": scientific_name,
                    }
                else:
                    return {
                        "species": [],
                        "count": 0,
                        "message": (
                            f"Species {scientific_name} exists but has no similar "
                            f"species in the database."
                        ),
                        "tried_scientific_name": scientific_name,
                    }

            species_names = [
                item.get("species", "").replace("_", " ")
                for item in similar_species
                if item.get("species")
            ]

            if not species_names:
                logger.warning(
                    "Found similar_species list but no valid species names extracted"
                )
                return {
                    "species": [],
                    "count": 0,
                    "message": "Found similar species but could not extract species names",
                    "tried_scientific_name": scientific_name,
                }

            logger.info(f"Found {len(species_names)} similar species for {scientific_name}")

            return {
                "species": species_names,
                "count": len(species_names),
                "similarity_scores": [
                    {
                        "species": item.get("species", "").replace("_", " "),
                        "distance": item.get("distance"),
                    }
                    for item in similar_species
                    if item.get("species")
                ],
                "reference_species": scientific_name,
            }

        except Exception as e:
            logger.error(f"Error in image similarity search: {e}", exc_info=True)
            return {
                "error": str(e),
                "species": [],
                "count": 0,
                "message": f"An error occurred while searching for similar species: {str(e)}",
            }

    async def _search_by_location(
        self,
        location: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Search for species by geographic location using GBIF occurrence data."""
        try:
            logger.info(f"Searching for species in location: {location}")

            # The GBIF service now returns a list (empty list if not found)
            species_names = self.gbif_service.search_by_location(
                location=location,
                limit=limit,
            )

            if not species_names:
                try:
                    count = self.gbif_service.count_entries()
                    if count is None or count == 0:
                        return {
                            "species": [],
                            "count": 0,
                            "message": (
                                "GBIF occurrence table appears to be empty or not loaded. "
                                "No location data available."
                            ),
                            "error": "no_data",
                        }
                except Exception as check_error:
                    logger.debug(f"Could not check table count: {check_error}")

                return {
                    "species": [],
                    "count": 0,
                    "message": (
                        f"No species found in location: {location}. "
                        f"The location may not be in the database, or "
                        f"location fields may not be populated."
                    ),
                    "location": location,
                    "suggestion": (
                        "Check that GBIF occurrence data has been properly ingested "
                        "with location information."
                    ),
                }

            logger.info(f"Found {len(species_names)} species in location: {location}")

            return {
                "species": species_names,
                "count": len(species_names),
                "location": location,
            }

        except Exception as e:
            logger.error(f"Error in location search: {e}", exc_info=True)
            return {
                "error": str(e),
                "species": [],
                "count": 0,
                "message": f"An error occurred while searching for location '{location}': {str(e)}",
            }

    async def _search_by_color(
        self,
        color_description: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search for species by color using CLIP text embeddings."""
        try:
            # Increase limit significantly to get more images, which yields more unique species
            # after filtering. The limit is for images, not species.
            image_limit = max(limit * 10, 3000)  # At least 300 images, or 10x the requested limit
            text_search = TextToImageSearch(
                request=self.request,
                query=color_description,
                limit=image_limit,
            )
            results = text_search.search()

            if not results:
                return {
                    "species": [],
                    "count": 0,
                    "message": f"No species found matching color: {color_description}",
                }

            species_set = set()
            for item in results:
                species = item.get("species", "").replace("_", " ")
                if species:
                    species_set.add(species)

            species_names = list(species_set)

            return {
                "species": species_names,
                "count": len(species_names),
                "color_query": color_description,
            }

        except Exception as e:
            logger.error(f"Error in color search: {e}", exc_info=True)
            return {"error": str(e), "species": [], "count": 0}

    async def _search_by_traits(
        self,
        canopy_affinity: Optional[str] = None,
        edge_affinity: Optional[str] = None,
        moisture_affinity: Optional[str] = None,
        disturbance_affinity: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Search for species by ecological traits."""
        try:
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
                return {
                    "species": [],
                    "count": 0,
                    "message": "No trait filters specified",
                }

            where_clause = " AND ".join(conditions)
            query = f"""
                SELECT DISTINCT Species
                FROM {self.leptraits_service.table}
                WHERE {where_clause}
                LIMIT {limit}
            """

            result = self.leptraits_service.db_client.execute(query).pl()

            if result.is_empty():
                return {
                    "species": [],
                    "count": 0,
                    "message": "No species found matching trait criteria",
                }

            species_names = result["Species"].to_list()

            return {
                "species": species_names,
                "count": len(species_names),
                "traits": {
                    "canopy_affinity": canopy_affinity,
                    "edge_affinity": edge_affinity,
                    "moisture_affinity": moisture_affinity,
                    "disturbance_affinity": disturbance_affinity,
                },
            }

        except Exception as e:
            logger.error(f"Error in trait search: {e}", exc_info=True)
            return {"error": str(e), "species": [], "count": 0}

    def _combine_search_results(self, species_lists: List[List[str]]) -> Dict[str, Any]:
        """Combine multiple species lists to find intersection."""
        if not species_lists or len(species_lists) == 0:
            return {"species": [], "count": 0}

        if len(species_lists) == 1:
            return {
                "species": species_lists[0],
                "count": len(species_lists[0]),
            }

        normalized_lists = [
            [s.lower().replace("_", " ") for s in lst]
            for lst in species_lists
        ]

        intersection = set(normalized_lists[0])
        for lst in normalized_lists[1:]:
            intersection = intersection.intersection(set(lst))

        return {
            "species": list(intersection),
            "count": len(intersection),
            "input_counts": [len(lst) for lst in species_lists],
        }

    def _parse_results(self, content: str, tool_results: List[Dict] | List[Any]) -> List[Dict[str, Any]]:
        """Parse agent response to extract final results.
        
        When multiple search tools are used, finds the INTERSECTION (species matching ALL criteria),
        not the union (species matching ANY criteria).
        
        Args:
            content: The final message content from the agent
            tool_results: Either list of tool result dicts (with 'content' key) or list of dicts with 'name' and 'result' keys
        """
        # Extract species lists from each tool result
        tool_species_lists = []
        tool_names = []
        
        for tool_result in tool_results:
            # Handle both formats: dict with 'content' key (from OpenAI) or dict with 'name' and 'result' keys
            if isinstance(tool_result, dict) and "content" in tool_result:
                # Format from OpenAI tool results
                content_str = str(tool_result.get("content", ""))
                tool_name = tool_result.get("name", "unknown")
                try:
                    result_data = json.loads(content_str)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(tool_result, dict) and "name" in tool_result and "result" in tool_result:
                # Format from full_results (with name and result keys)
                tool_name = tool_result.get("name", "unknown")
                result_data = tool_result.get("result")
            else:
                # Try to parse as raw result dict
                result_data = tool_result
                tool_name = "unknown"
            
            if not isinstance(result_data, dict):
                continue
                
            # Skip combine_search_results tool - it's just for orchestration
            if tool_name == "combine_search_results":
                continue
                
            if "species" in result_data:
                species_list = result_data.get("species", [])
                if species_list:
                    # Normalize species names
                    normalized_list = [
                        s.lower().replace("_", " ").strip()
                        for s in species_list
                        if s and str(s).strip()
                    ]
                    if normalized_list:
                        tool_species_lists.append(normalized_list)
                        tool_names.append(tool_name)
                        logger.info(f"Tool {tool_name} returned {len(normalized_list)} species")

        # If multiple search tools were used, find intersection (species matching ALL criteria)
        if len(tool_species_lists) > 1:
            logger.info(f"Combining results from {len(tool_species_lists)} tools: {tool_names}")
            combined = self._combine_search_results(tool_species_lists)
            species_list = combined.get("species", [])
            logger.info(f"Intersection found {len(species_list)} species matching all criteria")
        elif len(tool_species_lists) == 1:
            # Single tool - return all results
            species_list = tool_species_lists[0]
            logger.info(f"Single tool result: {len(species_list)} species")
        else:
            logger.warning("No species found in any tool results")
            return [{"message": content, "tool_results": len(tool_results)}]

        # Build results with source information
        results = []
        for species in species_list:
            results.append({
                "species": species,
                "sources": tool_names,
                "match_count": len(tool_names),
            })

        results.sort(key=lambda x: x["match_count"], reverse=True)
        logger.info(f"Returning {len(results)} final species")
        return results

    def _parse_direct_response(self, content: str) -> List[Dict[str, Any]]:
        """Parse a direct response without tool calls."""
        return [{"message": content}]
