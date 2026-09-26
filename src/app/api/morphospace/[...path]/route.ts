import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const RANKS = new Set(["all", "family", "genus", "species"]);

/**
 * Proxy for the backend's precomputed morphospaces.
 *
 * Passes the backend's cache headers through, so a browser holds a scope for
 * as long as the backend says it may, and lets Next compress the response: a
 * family's points are several hundred kilobytes of JSON that shrink by most
 * of that over gzip.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await params;
  if (path.length !== 2 || !RANKS.has(path[0])) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  const [rank, name] = path;
  try {
    const response = await fetch(
      `${API_HOST}/morphospace/${rank}/${encodeURIComponent(name)}`,
      { headers: { Accept: "application/json" }, cache: "no-store" },
    );
    const headers: Record<string, string> = {};
    for (const header of ["cache-control", "etag"]) {
      const value = response.headers.get(header);
      if (value) headers[header] = value;
    }
    return NextResponse.json(await response.json(), {
      status: response.status,
      headers,
    });
  } catch (error) {
    console.error(`Error fetching morphospace ${rank}/${name}:`, error);
    return NextResponse.json(
      { error: "Failed to fetch morphospace" },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }
}
