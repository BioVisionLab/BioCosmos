export interface MlResultItems {
  imgId: string;
  species: string;
  score?: number;
  distance?: number;
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

async function readErrorMessage(response: Response): Promise<string> {
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

  return `Color search request failed with status ${response.status}`;
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

async function searchSemantic(query: string): Promise<MlResultItems[]> {
  const response = await fetch(
    "/api/ml-search/agent?q=" + encodeURIComponent(query),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Agent search request failed with status ${response.status}`
    );
  }

  const json: unknown = await response.json();

  if (
    typeof json !== "object" ||
    json === null ||
    !("results" in json) ||
    !Array.isArray(json.results)
  ) {
    return [];
  }

  return json.results.filter(isBaseSearchResult).map((item) => ({
    imgId: item.imgId,
    species: item.species,
    score: typeof item.score === "number" ? item.score : undefined,
  }));
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

export { searchSemantic, searchFromImage, searchByColor };
