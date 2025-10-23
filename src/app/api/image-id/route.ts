/**
 * This route is responsible for serving images related to a specific species.
 * It fetches the image URLs from the database and returns them in the response.
 *
 * Query using image id and either returns the full resolution image or a thumbnail.
 */
import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const IMAGE_API_URL = `${API_HOST}/image/id`;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const imageId = searchParams.get("imageId");

  if (!imageId) {
    return NextResponse.json(
      { error: "Query parameter 'imageId' is required" },
      { status: 400 }
    );
  }

  console.log(`API: Fetching image for ID: ${imageId}`);

  try {
    const imageUri = `${IMAGE_API_URL}/${encodeURIComponent(imageId)}`;

    const response = await fetch(imageUri, {
      method: "GET",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch image: ${response.statusText}` },
        { status: response.status }
      );
    }

    // Stream the image binary data
    const imageBuffer = await response.arrayBuffer();

    // FileResponse sets the correct Content-Type automatically
    const contentType = response.headers.get("content-type") || "image/jpeg";

    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=31536000, immutable",
      },
    });
  } catch (error) {
    console.error(`Error fetching image ID ${imageId}:`, error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch image: ${errorMessage}` },
      { status: 500 }
    );
  }
}
