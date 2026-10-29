import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const RANKS = new Set([
  "order",
  "suborder",
  "superfamily",
  "family",
  "subfamily",
  "tribe",
  "subtribe",
  "genus",
  "subgenus",
]);

/**
 * The backend path of one taxon's literature. A genus takes its family as a
 * query parameter; a subgenus nests under its genus, without which it has no
 * route.
 */
function literaturePath(
  rank: string,
  name: string,
  context: string | undefined,
): string | null {
  const encoded = encodeURIComponent(name);

  if (rank === "subgenus") {
    return context
      ? `/genus/${encodeURIComponent(context)}/subgenus/${encoded}/literature`
      : null;
  }

  const query =
    rank === "genus" && context
      ? `?${new URLSearchParams({ family: context })}`
      : "";

  return `/${rank}/${encoded}/literature${query}`;
}

/**
 * Proxy for the backend literature search on a taxon above species.
 *
 * The species route's sibling, for the same reason: CrossRef is called from
 * the backend, which identifies the site, caches its answers and stays inside
 * its rate limits.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const rank = searchParams.get("rank")?.trim() ?? "";
  const name = searchParams.get("name")?.trim();
  const context = searchParams.get("context")?.trim() || undefined;
  const path =
    name && RANKS.has(rank) ? literaturePath(rank, name, context) : null;

  if (!path) {
    return NextResponse.json(
      {
        error:
          "Query parameters 'rank' (a rank above species) and 'name' are " +
          "required, and 'context' (the genus) for a subgenus",
      },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${API_HOST}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
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
