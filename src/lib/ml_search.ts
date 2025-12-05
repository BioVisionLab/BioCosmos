export interface MlResultItems {
  imgId: string;
  species: string;
  score: number;
}

async function searchSemantic(query: string): Promise<MlResultItems[]> {
  const response = await fetch(
    "/api/ml-search/agent?q=" + encodeURIComponent(query),
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
  const json = await response.json();
  const topResults = json as MlResultItems[];
  const otherResults = json as MlResultItems[];
  const results = topResults.length > 0 ? topResults : otherResults;
  // Iterate over result capturing imgId, species, and score (as distance)
  return results.map((item: any) => ({
    imgId: item.img_id,
    species: item.species,
    score: item.score,
  }));
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
