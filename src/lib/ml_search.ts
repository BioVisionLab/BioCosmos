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

export { searchSemantic };
