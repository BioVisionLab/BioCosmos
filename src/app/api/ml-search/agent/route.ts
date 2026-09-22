import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const AGENT_SEARCH = `${API_HOST}/search/agent`;

async function readBackendError(response: Response): Promise<string> {
  const fallback = `Agent search failed with status ${response.status}`;

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

  if (!query) {
    return NextResponse.json(
      { error: "Query parameter 'q' is required" },
      { status: 400 },
    );
  }

  console.log(`Forwarding agent search query "${query}" to ${AGENT_SEARCH}`);

  try {
    const response = await fetch(
      `${AGENT_SEARCH}?${new URLSearchParams({ q: query })}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        // Stop the backend work when the browser abandons the search.
        signal: request.signal,
      },
    );

    // Forward the backend's status (400 bad query, 502 planner failure,
    // 504 planner timeout, ...) instead of flattening everything to 503.
    if (!response.ok) {
      const errorMessage = await readBackendError(response);
      console.error(
        `Error from agent service (${response.status}): ${errorMessage}`,
      );
      return NextResponse.json(
        { error: errorMessage },
        { status: response.status },
      );
    }

    const data: unknown = await response.json();

    // Backend returns { query, total, results, message?, warnings? }
    if (
      typeof data !== "object" ||
      data === null ||
      !("results" in data) ||
      !Array.isArray(data.results)
    ) {
      console.error(
        "Unexpected response format from BIOCOSMOS BACKEND service. Expected { results: [] }.",
        data,
      );
      return NextResponse.json(
        { error: "Agent search returned an invalid response format." },
        { status: 502 },
      );
    }

    console.log(
      `Received ${data.results.length} results from BIOCOSMOS BACKEND service.`,
    );

    // Forward the full envelope to the frontend so it has query/total metadata
    return NextResponse.json(data);
  } catch (error) {
    if (request.signal.aborted) {
      return NextResponse.json(
        { error: "Request was cancelled." },
        { status: 499 },
      );
    }

    console.error("Error during agent search API call:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to contact agent service: ${errorMessage}` },
      { status: 503 },
    );
  }
}
