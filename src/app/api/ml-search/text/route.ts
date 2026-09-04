/**
 * Fully qualified URL of the local Python CLIP text-search endpoint, built from `API_HOST`.
 * The route forwards incoming queries to this service.
 *
 * @example
 * // If API_HOST = "http://localhost:8000"
 * // TEXT_SEARCH resolves to "http://localhost:8000/search/text"
 */

/**
 * Next.js (App Router) GET handler for semantic search.
 *
 * Expects a query string parameter `q` containing the natural-language search text.
 * Forwards the query and result limit to the local Python CLIP service and returns
 * the array of butterfly result objects produced by that service.
 *
 * Query parameters:
 * - q: string (required) — semantic search text.
 * - limit: integer (optional) — maximum results, between 1 and 50.
 *
 * Responses:
 * - 200: JSON array of result objects returned by the CLIP service.
 * - 400: { error: string } when `q` is missing or `limit` is invalid.
 * - 499: { error: string } when the incoming request is cancelled.
 * - 502: { error: string } when the backend returns an invalid success payload.
 * - 503: { error: string } when the CLIP service is unreachable.
 * - Other backend error statuses are forwarded with their error message.
 *
 * Notes:
 * - `URLSearchParams` URL-encodes `q` and `limit` before forwarding.
 * - Logs basic request/response details to the server console.
 *
 * Example requests:
 * @example
 * // Using a browser/location bar:
 * // /api/ml-search/text?q=red&limit=15
 *
 *
 * @param request - The incoming Next.js Request containing the URL with search params.
 * @returns A NextResponse containing JSON.
 */
import { NextResponse } from "next/server";

import { API_HOST } from "@/lib/config";

// Define the expected URL for the local Python CLIP service
const TEXT_SEARCH = `${API_HOST}/search/text`;
const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 50;

function parseLimit(rawLimit: string | null): number | null {
  if (rawLimit === null) return DEFAULT_LIMIT;
  if (rawLimit.trim() === "") return null;

  const limit = Number(rawLimit);
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_LIMIT) return null;
  return limit;
}

async function readBackendError(response: Response): Promise<string> {
  const fallback = `Backend text search failed with status ${response.status}`;

  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "error" in body &&
      typeof body.error === "string"
    ) {
      return body.error;
    }
  } catch {
    // The backend response was not JSON, so use the status fallback.
  }

  return fallback;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q")?.trim();
  const limit = parseLimit(searchParams.get("limit"));

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 },
    );
  }

  if (limit === null) {
    return NextResponse.json(
      {
        error: `Query parameter 'limit' must be an integer between 1 and ${MAX_LIMIT}`,
      },
      { status: 400 },
    );
  }

  const backendParams = new URLSearchParams({
    q: query,
    limit: String(limit),
  });

  console.log(
    `Forwarding semantic search query "${query}" with limit ${limit} to ${TEXT_SEARCH}`,
  );

  try {
    // Forward the request to the local Python service
    const clipResponse = await fetch(`${TEXT_SEARCH}?${backendParams}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal: request.signal,
    });

    // Check if the Python service responded successfully
    if (!clipResponse.ok) {
      const errorMessage = await readBackendError(clipResponse);
      console.error(
        `Error from CLIP service (${clipResponse.status}): ${errorMessage}`,
      );
      return NextResponse.json(
        { error: errorMessage },
        { status: clipResponse.status },
      );
    }

    // Parse the JSON response (expected to be an array of butterfly result objects)
    const results: unknown = await clipResponse.json();
    if (!Array.isArray(results)) {
      console.error(
        "Unexpected response format from BIOCOSMOS BACKEND service. Expected an array.",
        results,
      );
      return NextResponse.json(
        { error: "Backend text search returned an invalid response format." },
        { status: 502 },
      );
    }

    console.log(
      `Received ${results.length} results from BIOCOSMOS BACKEND service.`,
    );

    // Return the results from the Python service to the frontend
    return NextResponse.json(results);
  } catch (error) {
    if (request.signal.aborted) {
      return NextResponse.json(
        { error: "Request was cancelled." },
        { status: 499 },
      );
    }

    console.error("Error during semantic search API call:", error);
    // Handle fetch errors (e.g., service not running) or other issues
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to contact CLIP service: ${errorMessage}` },
      { status: 503 }, // 503 Service Unavailable
    );
  }
}
