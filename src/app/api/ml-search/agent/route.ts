import { NextResponse } from "next/server";

import { API_HOST } from "@/lib/config";
// Define the expected URL for the local Python CLIP service
const AGENT_SEARCH = `${API_HOST}/search/agent`;

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
    `Forwarding semantic search query \"${query}\" to ${AGENT_SEARCH}`
  );

  try {
    // Forward the request to the local Python service
    const response = await fetch(
      `${AGENT_SEARCH}?q=${encodeURIComponent(query)}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      }
    );

    // Check if the Python service responded successfully
    if (!response.ok) {
      let errorBody = "Unknown error from BIOCOSMOS BACKEND service";
      try {
        errorBody = await response.text(); // Try to get error text
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (_) {
        /* Ignore parsing errors */
      }
      console.error(
        `Error from CLIP service (${response.status}): ${errorBody}`
      );
      throw new Error(`CLIP service failed with status ${response.status}`);
    }

    // Parse the JSON response (expected to be an array of strings/identifiers)
    const results = await response.json();

    if (!Array.isArray(results)) {
      console.error(
        "Unexpected response format from BIOCOSMOS BACKEND service. Expected an array.",
        results
      );
      throw new Error(
        "Invalid response format from BIOCOSMOS BACKEND service."
      );
    }

    console.log(
      `Received ${results.length} results from BIOCOSMOS BACKEND service.`
    );

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
