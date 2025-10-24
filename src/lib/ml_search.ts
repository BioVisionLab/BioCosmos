export interface SemanticResultItem {
  imgId: string;
  species: string;
  distance: number;
}

async function searchSemantic(query: string): Promise<SemanticResultItem[]> {
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
  return results as SemanticResultItem[];
}

async function searchFromImage(file: File) {
  const formData = new FormData();
  formData.append("image", file); // Client sends as "image"

  try {
    const response = await fetch("/api/ml-search/image", {
      method: "POST",
      body: formData,
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
