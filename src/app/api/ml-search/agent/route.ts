import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

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

  console.log(`Forwarding agent search query "${query}" to ${AGENT_SEARCH}`);

  try {
    const response = await fetch(
      `${AGENT_SEARCH}?q=${encodeURIComponent(query)}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      }
    );

    if (!response.ok) {
      let errorBody = "Unknown error from BIOCOSMOS BACKEND service";
      try {
        errorBody = await response.text();
      } catch (_) {
        /* Ignore parsing errors */
      }
      console.error(`Error from agent service (${response.status}): ${errorBody}`);
      throw new Error(`Agent service failed with status ${response.status}`);
    }

    const data = await response.json();

    // Backend returns { query, total, results, message? }
    if (!data || typeof data !== "object" || !Array.isArray(data.results)) {
      console.error(
        "Unexpected response format from BIOCOSMOS BACKEND service. Expected { results: [] }.",
        data
      );
      throw new Error("Invalid response format from BIOCOSMOS BACKEND service.");
    }

    console.log(
      `Received ${data.total ?? data.results.length} results from BIOCOSMOS BACKEND service.`
    );

    // Forward the full envelope to the frontend so it has query/total metadata
    return NextResponse.json(data);

  } catch (error) {
    console.error("Error during agent search API call:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to contact agent service: ${errorMessage}` },
      { status: 503 }
    );
  }
}
