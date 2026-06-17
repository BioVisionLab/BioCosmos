// Proxy API route that forwards taxon search queries to the backend.
// Validates the `q` query parameter and returns taxon classification results.
import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const DB_SEARCH_ENDPOINT = `${API_HOST}/search/db`;

const LIMIT = 50;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q");
  const field = searchParams.get("field") || "all";
  const page = searchParams.get("page") || "1";

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(
      `${DB_SEARCH_ENDPOINT}?q=${encodeURIComponent(query)}&field=${encodeURIComponent(field)}&page=${encodeURIComponent(page)}&limit=${LIMIT}`
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
