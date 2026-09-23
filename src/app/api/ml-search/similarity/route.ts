import { NextResponse } from "next/server";
import { SimilarSpeciesList } from "@/lib/similarSpecies";
import { API_HOST } from "@/lib/config";

const SIMILARITY_SERVICE_URL = `${API_HOST}/species`;

/**
 * How long to wait on the backend before giving up.
 *
 * The similarity search is a vector scan with no ANN index behind it, so a
 * cold one can run for a long time. Unbounded, this route held a socket open
 * for the whole of it — including after the browser had navigated away — and
 * the species page's own image requests queued behind it against the
 * six-connection-per-origin budget. A bounded failure is better than a page
 * that never finishes painting.
 */
const UPSTREAM_TIMEOUT_MS = 15_000;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");
  const side = searchParams.get("side");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  if (side && side !== "dorsal" && side !== "ventral") {
    return NextResponse.json(
      { error: "Query parameter 'side' must be 'dorsal' or 'ventral'" },
      { status: 400 }
    );
  }

  // The panel fetches one view per request so each section paints as soon as
  // its own search lands, rather than both waiting on the slower one.
  const upstream = side
    ? `${SIMILARITY_SERVICE_URL}/${encodeURIComponent(species)}/similar?side=${side}`
    : `${SIMILARITY_SERVICE_URL}/${encodeURIComponent(species)}/similar`;

  try {
    const response = await fetch(
      upstream,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        // Either the reader leaving or the deadline passing releases the
        // upstream socket. `request.signal` alone would not cover a backend
        // that simply never answers.
        signal: AbortSignal.any([
          request.signal,
          AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
        ]),
      }
    );
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error(
        `Error fetching similarity data: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch similarity data: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status, headers: { "Cache-Control": "no-store" } }
      );
    }
    const similarityData: SimilarSpeciesList = await response.json();
    // Pass the backend's own policy through rather than inventing one here,
    // so the two cannot drift. A response that arrived without one is not
    // cached at all.
    return NextResponse.json(similarityData, {
      headers: {
        "Cache-Control":
          response.headers.get("Cache-Control") ?? "no-store",
      },
    });
  } catch (error) {
    // An abort is the reader navigating away or the deadline passing, not a
    // fault worth a stack trace in the log.
    if (error instanceof DOMException && error.name === "AbortError") {
      return NextResponse.json(
        { error: "Similarity search timed out" },
        { status: 504, headers: { "Cache-Control": "no-store" } }
      );
    }
    console.error(
      `Error fetching similarity data for species ${species}:`,
      error
    );
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch similarity data: ${errorMessage}` },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}
