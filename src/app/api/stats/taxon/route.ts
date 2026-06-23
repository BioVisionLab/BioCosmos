import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const TAXON_STATS_URL = `${API_HOST}/stats/taxon`;

export async function GET(): Promise<NextResponse> {
  try {
    const response = await fetch(TAXON_STATS_URL, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const errorData = await response.json();
      return NextResponse.json(
        { error: errorData.error || response.statusText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch taxon stats: ${message}` },
      { status: 500 }
    );
  }
}
