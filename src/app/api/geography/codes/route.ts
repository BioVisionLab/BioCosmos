import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const GEOGRAPHY_CODES_URL = `${API_HOST}/geography/codes`;

export async function GET(): Promise<NextResponse> {
  try {
    const response = await fetch(GEOGRAPHY_CODES_URL, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: response.statusText },
        { status: response.status },
      );
    }

    const data = await response.json();
    // The descriptions only change when geoharmonize itself changes, so this
    // is safe to hold for a while rather than refetching per page view.
    return NextResponse.json(data, {
      headers: { "Cache-Control": "public, max-age=3600" },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch geography codes: ${message}` },
      { status: 500 },
    );
  }
}
