import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const IMAGE_SEARCH = `${API_HOST}/search/image`;

export async function POST(request: Request) {
  try {
    // Parse the incoming form data from the client
    const formData = await request.formData();
    const image = formData.get("image") as File;

    if (!image) {
      return NextResponse.json(
        { error: "Image file is required" },
        { status: 400 }
      );
    }

    console.log(
      `Forwarding image search "${image.name}" (${image.type}) to ${IMAGE_SEARCH}`
    );

    // Create a new FormData object to send to FastAPI
    // IMPORTANT: Use "file" as the parameter name to match FastAPI's UploadFile parameter
    const fastApiFormData = new FormData();
    fastApiFormData.append("file", image, image.name);

    // Forward the request to your FastAPI service
    const response = await fetch(IMAGE_SEARCH, {
      method: "POST",
      body: fastApiFormData,
      // Don't set Content-Type header - browser adds it automatically with boundary
    });

    // Check if the FastAPI service responded successfully
    if (!response.ok) {
      let errorBody = "Unknown error from BIOCOSMOS BACKEND service";
      try {
        errorBody = await response.text();
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (_) {
        /* Ignore parsing errors */
      }
      console.error(
        `Error from BIOCOSMOS BACKEND service (${response.status}): ${errorBody}`
      );
      if (errorBody.includes("Invalid file type")) {
        throw new Error(
          "Invalid file type. Please upload a valid image. Supported formats: JPEG, JPG, PNG, GIF, WEBP."
        );
      } else {
        throw new Error(
          `BIOCOSMOS BACKEND service failed with status ${response.status}`
        );
      }
    }
    // Parse the JSON response
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

    return NextResponse.json(results);
  } catch (error) {
    console.error("Error during image search API call:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json({ error: errorMessage }, { status: 503 });
  }
}
