import { NextResponse } from "next/server";
import { SpeciesData } from "@/lib/speciesData";
import { API_HOST } from "@/lib/config";

const TAXONOMY_SERVICE_URL = `${API_HOST}/taxon`;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching taxonomy data for species: ${species}`);
  try {
    const response = await fetch(
      `${TAXONOMY_SERVICE_URL}?q=${encodeURIComponent(species)}`,
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
        `Error fetching taxonomy data: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch taxonomy data: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }
    const taxonomyData: SpeciesData = await response.json();
    return NextResponse.json(taxonomyData);
  } catch (error) {
    console.error(
      `Error fetching taxonomy data for species ${species}:`,
      error
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch taxonomy data: ${errorMessage}` },
      { status: 500 }
    );
  }
}
