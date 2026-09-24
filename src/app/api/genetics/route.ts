import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

/**
 * Proxy for the backend genetics summary.
 *
 * NCBI is called from the backend, which identifies the site to NCBI, holds
 * the API key, caches its answers and stays inside its rate limits. The
 * browser used to call NCBI directly, anonymously and uncached.
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
      `${API_HOST}/species/${encodeURIComponent(species)}/genetics`,
      { method: "GET", headers: { Accept: "application/json" } },
    );
    const data = await response.json();
    // The backend sets the policy: a day for a complete summary, minutes for
    // a partial one, nothing for an error or a busy 503.
    const cacheControl = response.headers.get("Cache-Control") ?? "no-store";
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": cacheControl },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch genetic data: ${message}` },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
