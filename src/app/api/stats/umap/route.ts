import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const UMAP_API_URL = `${API_HOST}/stats/umap`;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching UMAP embeddings for species: ${species}`);
  try {
    const response = await fetch(
      `${UMAP_API_URL}/${encodeURIComponent(species)}`,
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
        `Error fetching UMAP embeddings: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch UMAP embeddings: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }
    const umapData = await response.json();
    return NextResponse.json(umapData);
  } catch (error) {
    console.error(
      `Error fetching UMAP embeddings for species ${species}:`,
      error
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch UMAP embeddings: ${errorMessage}` },
      { status: 500 }
    );
  }
}
