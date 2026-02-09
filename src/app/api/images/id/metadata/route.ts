import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";

const IMAGE_API_URL = `${API_HOST}/image/id`;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const imageId = searchParams.get("imageId");

  if (!imageId) {
    return NextResponse.json({ error: "Query parameter 'imageId' is required" }, { status: 400 });
  }

  try {
    const metaUri = `${IMAGE_API_URL}/${encodeURIComponent(imageId)}/metadata`;
    const response = await fetch(metaUri, { method: "GET" });
    if (!response.ok) {
      const err = await response.text();
      return NextResponse.json({ error: `Failed to fetch image metadata: ${response.statusText} ${err}` }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: `Failed to fetch image metadata: ${msg}` }, { status: 500 });
  }
}
