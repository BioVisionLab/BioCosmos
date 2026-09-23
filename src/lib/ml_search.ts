export interface MlResultItems {
  imgId: string;
  species: string;
  score?: number;
  distance?: number;
}

export interface SemanticSearchResult {
  imgId: string;
  species: string;
  tool_names: string[];
}

export interface ColorSearchResult extends MlResultItems {
  distance: number;
  source_db: string;
  class_dv: string;
}

function isBaseSearchResult(
  value: unknown,
): value is Record<string, unknown> & { imgId: string; species: string } {
  if (typeof value !== "object" || value === null) return false;

  const result = value as Record<string, unknown>;
  return typeof result.imgId === "string" && typeof result.species === "string";
}

function isColorSearchResult(value: unknown): value is ColorSearchResult {
  if (typeof value !== "object" || value === null) return false;

  const result = value as Record<string, unknown>;
  return (
    typeof result.imgId === "string" &&
    typeof result.species === "string" &&
    typeof result.distance === "number" &&
    Number.isFinite(result.distance) &&
    typeof result.source_db === "string" &&
    typeof result.class_dv === "string"
  );
}

async function readErrorMessage(
  response: Response,
  label = "Color search",
): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "error" in body &&
      typeof body.error === "string"
    ) {
      return body.error;
    }
  } catch {
    // The response did not contain JSON, so use the status fallback below.
  }

  return `${label} request failed with status ${response.status}`;
}

async function searchByColor(
  color: string,
  limit: number,
  signal?: AbortSignal,
): Promise<ColorSearchResult[]> {
  const query = color.trim();
  if (!query) {
    throw new Error("A color is required to search for butterflies.");
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
    throw new Error("Color search limit must be an integer between 1 and 50.");
  }

  const searchParams = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const response = await fetch(`/api/ml-search/text?${searchParams}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const results: unknown = await response.json();
  if (!Array.isArray(results) || !results.every(isColorSearchResult)) {
    throw new Error("Color search returned an unexpected response format.");
  }

  return results;
}

export interface SemanticSearchPage {
  query: string;
  searchId: string | null;
  total: number;
  offset: number;
  hasMore: boolean;
  results: SemanticSearchResult[];
}

/** The backend no longer holds the cached search a page was requested from. */
class SearchExpiredError extends Error {}

/**
 * Fetch one page of agent search results.
 *
 * The first call (no `searchId`) runs the search; pass the returned
 * `searchId` with a later `offset` to page through it without re-running
 * the planner. `refresh` bypasses the backend's cache of repeated queries.
 */
async function searchSemantic(
  query: string,
  options: {
    searchId?: string | null;
    offset?: number;
    refresh?: boolean;
    signal?: AbortSignal;
  } = {},
): Promise<SemanticSearchPage> {
  const { searchId, offset = 0, refresh = false, signal } = options;
  const params = new URLSearchParams();
  if (searchId) {
    params.set("search_id", searchId);
  } else {
    params.set("q", query);
  }
  if (offset > 0) params.set("offset", String(offset));
  if (refresh) params.set("refresh", "true");

  const response = await fetch(`/api/ml-search/agent?${params}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    const message = await readErrorMessage(response, "Agent search");
    throw response.status === 410
      ? new SearchExpiredError(message)
      : new Error(message);
  }

  const json: unknown = await response.json();

  if (
    typeof json !== "object" ||
    json === null ||
    !("results" in json) ||
    !Array.isArray(json.results)
  ) {
    return {
      query,
      searchId: null,
      total: 0,
      offset,
      hasMore: false,
      results: [],
    };
  }

  const body = json as Record<string, unknown> & { results: unknown[] };
  const results = body.results.filter(isBaseSearchResult).map((item) => ({
    imgId: item.imgId,
    species: item.species,
    tool_names: Array.isArray(item.tool_names)
      ? item.tool_names.filter((name): name is string => typeof name === "string")
      : [],
  }));

  return {
    query: typeof body.query === "string" ? body.query : query,
    searchId: typeof body.searchId === "string" ? body.searchId : null,
    total: typeof body.total === "number" ? body.total : results.length,
    offset: typeof body.offset === "number" ? body.offset : offset,
    hasMore: body.hasMore === true,
    results,
  };
}

async function searchFromImage(data: FormData): Promise<MlResultItems[]> {
  try {
    const response = await fetch("/api/ml-search/image", {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Upload failed");
    }

    const results: unknown = await response.json();
    if (!Array.isArray(results)) {
      throw new Error("Image search returned an unexpected response format.");
    }

    return results.filter(isBaseSearchResult).map((item) => ({
      imgId: item.imgId,
      species: item.species,
      // Pass the raw metric correctly as distance instead of arbitrarily casting to a similarity score
      distance: typeof item.distance === "number" ? item.distance : undefined,
    }));
  } catch (error) {
    console.error("Error uploading image:", error);
    throw error;
  }
}

export { searchSemantic, searchFromImage, searchByColor, SearchExpiredError };
