import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

/**
 * Proxy for the backend literature search.
 *
 * CrossRef is called from the backend, which identifies the site to CrossRef,
 * caches its answers and stays inside its rate limits. The browser used to
 * call CrossRef directly, anonymously and uncached, from every visitor.
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
      `${API_HOST}/species/${encodeURIComponent(species)}/literature`,
      { method: "GET", headers: { Accept: "application/json" } },
    );
    const data = await response.json();
    // The backend sets the policy: a day for a complete list, minutes for a
    // partial one, nothing for an error.
    const cacheControl = response.headers.get("Cache-Control") ?? "no-store";
    return NextResponse.json(data, {
      status: response.status,
      headers: { "Cache-Control": cacheControl },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch literature: ${message}` },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
