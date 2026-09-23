import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

/**
 * Proxy for the backend species taxonomy: nomenclature, name usages and type
 * material from the ingested Catalogue of Life release.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species")?.trim();

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(
      `${API_HOST}/species/${encodeURIComponent(species)}/taxonomy`,
      { method: "GET", headers: { Accept: "application/json" } },
    );
    const data = await response.json();
    // The backend sets the policy: a month for a hit, nothing for a miss.
    const cacheControl = response.headers.get("Cache-Control") ?? "no-store";
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": cacheControl },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch taxonomy: ${message}` },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
