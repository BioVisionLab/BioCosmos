import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const SPECIES_API_URL = `${API_HOST}/species`;

/**
 * The georeferenced specimens of one species, for the distribution map.
 *
 * A 404 means the species has no usable coordinate, which is an ordinary
 * outcome for the map rather than an error, so it is passed on as an empty
 * list.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(
      `${SPECIES_API_URL}/${encodeURIComponent(species)}/coordinates`,
      { method: "GET", headers: { Accept: "application/json" } },
    );
    if (response.status === 404) {
      return NextResponse.json({ total: 0, truncated: false, points: [] });
    }
    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch coordinates: ${response.statusText}` },
        { status: response.status },
      );
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    console.error(`Error fetching coordinates for species ${species}:`, error);
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch coordinates: ${message}` },
      { status: 500 },
    );
  }
}
