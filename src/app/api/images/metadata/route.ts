import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const IMAGE_API_URL = `${API_HOST}/image`;

/**
 * This route is responsible for serving images related to a specific species.
 * It fetches the image IDs from the database and returns them in the response.
 *
 * Query using species scientific name.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("scientificName");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'scientificName' is required" },
      { status: 400 },
    );
  }

  try {
    // Forward paging params so the backend can return a single page of IDs.
    // Malformed values are dropped rather than forwarded.
    const paging = new URLSearchParams();
    for (const key of ["limit", "offset"] as const) {
      const raw = searchParams.get(key);
      if (raw === null) continue;
      const parsed = Number(raw);
      if (Number.isInteger(parsed) && parsed >= 0) {
        paging.set(key, String(parsed));
      }
    }
    const query = paging.size > 0 ? `?${paging.toString()}` : "";
    const metadataUri = `${IMAGE_API_URL}/${encodeURIComponent(
      species,
    )}/metadata${query}`;
    const response = await fetch(metadataUri, {
      method: "GET",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch image metadata: ${response.statusText}` },
        { status: response.status },
      );
    }

    const metadata = await response.json();

    return NextResponse.json(metadata);
  } catch (error) {
    console.error(
      `Error fetching image metadata for species ${species}:`,
      error,
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch image metadata: ${errorMessage}` },
      { status: 500 },
    );
  }
}
