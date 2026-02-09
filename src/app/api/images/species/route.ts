// Proxy API route that fetches a species image (thumbnail or high-resolution)
// from the backend image service and returns it with appropriate headers.
import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const IMAGE_API_URL = `${API_HOST}/image`;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("scientificName");
  const type = searchParams.get("type") === "thumbnail" ? "thumbnail" : "full";

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching image for species: ${species}`);

  try {
    const imageUri = `${IMAGE_API_URL}/${encodeURIComponent(species)}${
      type === "thumbnail" ? "/thumbnail" : "/high-resolution"
    }`;

    const response = await fetch(imageUri, {
      method: "GET",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch image: ${response.statusText}` },
        { status: response.status }
      );
    }

    // Get the image as an array buffer
    const imageBuffer = await response.arrayBuffer();

    // Get content type from FastAPI response or default to e.g. image/webp
    const contentType = response.headers.get("content-type") || "image/webp";

    // Return image with proper headers
    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=31536000, immutable",
      },
    });
  } catch (error) {
    console.error(`Error fetching ${type} for species ${species}:`, error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch image: ${errorMessage}` },
      { status: 500 }
    );
  }
}
