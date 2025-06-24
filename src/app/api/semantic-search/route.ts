import { NextResponse } from "next/server";

// Define the expected URL for the local Python CLIP service
const CLIP_SERVICE_URL = "http://127.0.0.1:8000/text-search"; // Adjust port if needed

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
    `Forwarding semantic search query \"${query}\" to ${CLIP_SERVICE_URL}`
  );

  try {
    // Forward the request to the local Python service
    const clipResponse = await fetch(
      `${CLIP_SERVICE_URL}?q=${encodeURIComponent(query)}`,
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
