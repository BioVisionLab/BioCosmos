import { NextResponse } from "next/server";

const GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search";
const GBIF_LIMIT = 200;
const CACHE_TTL_MS = 1000 * 60 * 60 * 24; // 24 hours

const cache = new Map<string, { data: unknown[]; timestamp: number }>();

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  const cacheKey = species.trim().toLowerCase();
  const cached = cache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return NextResponse.json({ results: cached.data });
  }

  console.log(`API: Fetching GBIF occurrences for species: ${species}`);
  try {
    const response = await fetch(
      `${GBIF_API_URL}?scientificName=${encodeURIComponent(
        species.trim()
      )}&limit=${GBIF_LIMIT}&hasCoordinate=true&hasGeospatialIssue=false`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      console.error(
        `Error fetching GBIF occurrences: ${response.status} - ${response.statusText}`
      );
      return NextResponse.json(
        { error: `GBIF API error: ${response.statusText}`, results: [] },
        { status: response.status }
      );
    }

    const data = await response.json();
    cache.set(cacheKey, { data: data.results, timestamp: Date.now() });
    return NextResponse.json({ results: data.results });
  } catch (error) {
    console.error(
      `Error fetching GBIF occurrences for species ${species}:`,
      error
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch GBIF occurrences: ${errorMessage}`, results: [] },
      { status: 500 }
    );
  }
}
