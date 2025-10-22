import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching specimens for species: ${species}`);
  try {
    const response = await fetch(
      `${API_HOST}/taxon/${encodeURIComponent(species)}/specimens`,
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
        `Error fetching specimens: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch specimens: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }
    const specimens = await response.json();
    return NextResponse.json(specimens);
  } catch (error) {
    console.error(`Error fetching specimens for species ${species}:`, error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch specimens: ${errorMessage}` },
      { status: 500 }
    );
  }
}
