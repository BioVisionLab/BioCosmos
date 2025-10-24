/**
 * Fully qualified URL of the local Python CLIP text-search endpoint, built from `API_HOST`.
 * The route forwards incoming queries to this service.
 *
 * @example
 * // If API_HOST = "http://localhost:5001"
 * // TEXT_SEARCH resolves to "http://localhost:5001/text-search"
 */

/**
 * Next.js (App Router) GET handler for semantic search.
 *
 * Expects a query string parameter `q` containing the natural-language search text.
 * Forwards the query to a local Python CLIP service and returns the array of identifiers
 * (strings) produced by that service.
 *
 * Query parameters:
 * - q: string (required) — semantic search text.
 *
 * Responses:
 * - 200: JSON array of strings returned by the CLIP service.
 * - 400: { error: string } when `q` is missing.
 * - 503: { error: string } when the CLIP service is unreachable or returns a non-OK status.
 *
 * Notes:
 * - The handler URL-encodes `q` before forwarding.
 * - Logs basic request/response details to the server console.
 *
 * Example requests:
 * @example
 * // Using a browser/location bar:
 * // /api/semantic-search?q=danaus%20plexippus
 *
 *
 * @param request - The incoming Next.js Request containing the URL with search params.
 * @returns A NextResponse containing JSON.
 */
import { NextResponse } from "next/server";

import { API_HOST } from "@/lib/config";
// Define the expected URL for the local Python CLIP service
const TEXT_SEARCH = `${API_HOST}/search/text`;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q");

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 }
    );
  }

  console.log(
    `Forwarding semantic search query \"${query}\" to ${TEXT_SEARCH}`
  );

  try {
    // Forward the request to the local Python service
    const clipResponse = await fetch(
      `${TEXT_SEARCH}?q=${encodeURIComponent(query)}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );

    // Check if the Python service responded successfully
    if (!clipResponse.ok) {
      let errorBody = "Unknown error from CLIP service";
      try {
        errorBody = await clipResponse.text(); // Try to get error text
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (_) {
        /* Ignore parsing errors */
      }
      console.error(
        `Error from CLIP service (${clipResponse.status}): ${errorBody}`
      );
      throw new Error(`CLIP service failed with status ${clipResponse.status}`);
    }

    // Parse the JSON response (expected to be an array of strings/identifiers)
    const results = await clipResponse.json();

    if (!Array.isArray(results)) {
      console.error(
        "Unexpected response format from CLIP service. Expected an array.",
        results
      );
      throw new Error("Invalid response format from CLIP service.");
    }

    console.log(`Received ${results.length} results from CLIP service.`);

    // Return the results from the Python service to the frontend
    return NextResponse.json(results);
  } catch (error) {
    console.error("Error during semantic search API call:", error);
    // Handle fetch errors (e.g., service not running) or other issues
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to contact CLIP service: ${errorMessage}` },
      { status: 503 }
    ); // 503 Service Unavailable
  }
}
