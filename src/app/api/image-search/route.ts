import { NextResponse } from "next/server";

import { API_HOST } from "@/lib/config";
// Define the expected URL for the image search endpoint on the Python service
const IMAGE_SEARCH = `${API_HOST}/img-search`;

export async function POST(request: Request) {
  let base64Image: string;

  // Extract the base64 image string from the request body
  try {
    const body = await request.json();
    if (
      !body.image ||
      typeof body.image !== "string" ||
      !body.image.startsWith("data:image/")
    ) {
      return NextResponse.json(
        { error: "Invalid request body: base64 image string required." },
        { status: 400 }
      );
    }
    base64Image = body.image;
  } catch (e) {
    return NextResponse.json(
      { error: "Invalid JSON request body." },
      { status: 400 }
    );
  }

  console.log(`Forwarding image search request to ${IMAGE_SEARCH}`);

  try {
    // Forward the request to the local Python service
    const clipResponse = await fetch(IMAGE_SEARCH, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ image: base64Image }), // Send the base64 string
      // signal: AbortSignal.timeout(15000) // Optional: longer timeout for image processing
    });

    // Check if the Python service responded successfully
    if (!clipResponse.ok) {
      let errorBody = "Unknown error from CLIP service (image search)";
      try {
        errorBody = await clipResponse.text();
      } catch (_) {
        /* Ignore parsing errors */
      }
      console.error(
        `Error from CLIP image search service (${clipResponse.status}): ${errorBody}`
      );
      throw new Error(
        `CLIP service (image search) failed with status ${clipResponse.status}`
      );
    }

    // Parse the JSON response (expected to be an array of {species_folder, best_image_filename})
    const results = await clipResponse.json();

    if (!Array.isArray(results)) {
      console.error(
        "Unexpected response format from CLIP image service. Expected an array.",
        results
      );
      throw new Error("Invalid response format from CLIP image service.");
    }

    console.log(`Received ${results.length} results from CLIP image service.`);

    // Return the results from the Python service to the frontend
    return NextResponse.json(results);
  } catch (error) {
    console.error("Error during image search API call:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      {
        error: `Failed to contact CLIP service for image search: ${errorMessage}`,
      },
      { status: 503 }
    ); // 503 Service Unavailable
  }
}
