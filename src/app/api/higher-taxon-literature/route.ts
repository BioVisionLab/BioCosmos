import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const RANKS = new Set(["order", "family", "genus"]);

/**
 * Proxy for the backend literature search on an order, family or genus.
 *
 * The species route's sibling, for the same reason: CrossRef is called from
 * the backend, which identifies the site, caches its answers and stays inside
 * its rate limits.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const rank = searchParams.get("rank")?.trim() ?? "";
  const name = searchParams.get("name")?.trim();
  const family = searchParams.get("family")?.trim();

  if (!RANKS.has(rank) || !name) {
    return NextResponse.json(
      {
        error:
          "Query parameters 'rank' (order, family or genus) and 'name' are required",
      },
      { status: 400 },
    );
  }

  try {
    // Only the genus route reads a family; see fetchHigherTaxonLiterature.
    const query =
      rank === "genus" && family ? `?${new URLSearchParams({ family })}` : "";
    const response = await fetch(
      `${API_HOST}/${rank}/${encodeURIComponent(name)}/literature${query}`,
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
      { error: message },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
