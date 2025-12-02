/*
Check backend status
*/
import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

export async function GET(): Promise<NextResponse> {
  try {
    const response = await fetch(`${API_HOST}/status`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        `Error checking status: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Status check failed: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }

    const statusData = await response.json();
    return NextResponse.json(statusData);
  } catch (error) {
    console.error("Error checking status:", error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Status check failed: ${errorMessage}` },
      { status: 500 }
    );
  }
}
