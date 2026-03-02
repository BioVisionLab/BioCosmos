export interface DbResultItems {
  species: string;
  matched_fields: string[];
  score: number;
}

async function searchDatabase(query: string): Promise<DbResultItems[]> {
  const response = await fetch(
    "/api/db-search?q=" + encodeURIComponent(query),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Database search request failed with status ${response.status}`
    );
  }

  const json = await response.json();

  if (!json.results || json.results.length === 0) {
    return [];
  }

  return json.results.map((item: any) => ({
    matched_fields: item.matched_fields,
    score: item.score,
    species: item.species,
  }));
}

export { searchDatabase };