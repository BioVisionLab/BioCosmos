/*
This route is responsible for serving images related to a specific species.
It fetches the image URLs from the database and returns them in the response.

Query using image id and either returns the full resolution image or a thumbnail.
*/
// import { NextResponse } from "next/server";
import { API_HOST } from "@/lib/config";
import { NextResponse } from "next/server";

const IMAGE_API_URL = `${API_HOST}/taxon`;

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const speciesName = searchParams.get("species");
  const type = searchParams.get("type") === "thumbnail" ? "thumbnail" : "full";

  if (!speciesName) {
    throw new Error("Query parameter 'species' is required");
  }

  // Validate the type parameter
  if (type !== "thumbnail" && type !== "full") {
    throw new Error("Invalid type parameter. Must be 'thumbnail' or 'image'.");
  }

  console.log(`API: Fetching ${type} for species: ${speciesName}`);

  try {
    const imageUri = `${IMAGE_API_URL}/${encodeURIComponent(speciesName)}${
      type === "thumbnail" ? "/thumbnail" : ""
    }`;
    const response = await fetch(imageUri, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error(
        `Error fetching ${type}: ${response.status} - ${JSON.stringify(
          errorData
        )}`
      );
      return NextResponse.json(
        {
          error: `Failed to fetch ${type}: ${
            errorData.error || response.statusText
          }`,
        },
        { status: response.status }
      );
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    console.error(`Error fetching ${type} for species ${speciesName}:`, error);
    const errorMessage =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { error: `Failed to fetch image: ${errorMessage}` },
      { status: 500 }
    );
  }
}
