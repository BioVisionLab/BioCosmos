import { API_HOST } from "@/lib/config";
import { SpeciesData } from "@/lib/speciesData";
import { NextResponse } from "next/server";

const DB_SEARCH_ENDPOINT = `${API_HOST}/search/taxon`;

const LIMIT = 20;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q");

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(
      `${DB_SEARCH_ENDPOINT}?q=${encodeURIComponent(query)}&limit=${LIMIT}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch taxon data: ${response.statusText}`);
    }
    const taxonData = await response.json();

    return NextResponse.json(taxonData);
  } catch (error) {
    console.error("Search API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch species data" },
      { status: 500 }
    );
  }
}
