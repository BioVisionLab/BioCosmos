export interface MlResultItems {
  imgId: string;
  species: string;
  distance: number;
}

async function searchSemantic(query: string): Promise<MlResultItems[]> {
  const response = await fetch(
    "/api/ml-search/text?q=" + encodeURIComponent(query),
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Semantic search request failed with status ${response.status}`
    );
  }
  const results = await response.json();
  return results as MlResultItems[];
}

async function searchFromImage(data: FormData): Promise<MlResultItems[]> {
  try {
    const response = await fetch("/api/ml-search/image", {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Upload failed");
    }

    const results = await response.json();
    return results;
  } catch (error) {
    console.error("Error uploading image:", error);
    throw error;
  }
}

export { searchSemantic, searchFromImage };
