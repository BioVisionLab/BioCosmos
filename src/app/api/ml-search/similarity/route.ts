import { NextResponse } from "next/server";
import { SpeciesData } from "@/lib/speciesData";
import { API_HOST } from "@/lib/config";
import { headers } from "next/headers";

const SIMILARITY_SERVICE_URL = `${API_HOST}/species`;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching similarity data for species: ${species}`);
  try {
    const response = await fetch(
      `${SIMILARITY_SERVICE_URL}/${encodeURIComponent(species)}/similar`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );
    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        `Error fetching similarity data: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch similarity data: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }
    const similarityData: SpeciesData = await response.json();
    // Add caching logic to return
    return NextResponse.json(similarityData);
  } catch (error) {
    console.error(
      `Error fetching similarity data for species ${species}:`,
      error
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch similarity data: ${errorMessage}` },
      { status: 500 }
    );
  }
}
