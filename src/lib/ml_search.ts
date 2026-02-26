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
      headers: { Accept: "application/json" },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Agent search request failed with status ${response.status}`
    );
  }

  const json = await response.json();

  if (!json.results || json.results.length === 0) {
    return [];
  }

  return json.results.map((item: any) => ({
    imgId: item.imgId,       // ? camelCase from Pydantic alias
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
