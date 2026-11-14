/**
 * Serves one image by its id, either full resolution or a thumbnail.
 */
import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";
import { proxyImage } from "@/lib/imageProxy";

const IMAGE_API_URL = `${API_HOST}/image/id`;

export async function GET(request: Request): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const imageId = searchParams.get("imageId");
  const type = searchParams.get("type") === "thumbnail" ? "thumbnail" : "full";

  if (!imageId) {
    return NextResponse.json(
      { error: "Query parameter 'imageId' is required" },
      { status: 400 },
    );
  }

  const imageUri = `${IMAGE_API_URL}/${encodeURIComponent(imageId)}${
    type === "thumbnail" ? "/thumbnail" : ""
  }`;

  return proxyImage(imageUri, request);
}
