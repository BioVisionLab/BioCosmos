import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const EMBEDDINGS_API_URL = `${API_HOST}/stats/embeddings`;

export async function GET(): Promise<NextResponse> {
  console.log("API: Fetching embedding distributions");
  try {
    const response = await fetch(EMBEDDINGS_API_URL, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        `Error fetching embedding distributions: ${
          response.status
        } - ${JSON.stringify(errorData)}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch embedding distributions: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }
    const embeddingStats = await response.json();
    return NextResponse.json(embeddingStats);
  } catch (error) {
    console.error("Error fetching embedding distributions:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch embedding distributions: ${errorMessage}` },
      { status: 500 }
    );
  }
}
