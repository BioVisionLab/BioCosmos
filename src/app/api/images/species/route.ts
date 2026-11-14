/**
 * Serves a species' representative image, thumbnail or high resolution.
 */
import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";
import { proxyImage } from "@/lib/imageProxy";

const IMAGE_API_URL = `${API_HOST}/image`;

export async function GET(request: Request): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("scientificName");
  const type = searchParams.get("type") === "thumbnail" ? "thumbnail" : "full";

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'scientificName' is required" },
      { status: 400 },
    );
  }

  const imageUri = `${IMAGE_API_URL}/${encodeURIComponent(species)}${
    type === "thumbnail" ? "/thumbnail" : "/high-resolution"
  }`;

  return proxyImage(imageUri, request);
}
