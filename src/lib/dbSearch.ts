export interface DbResultItems {
  imgId: string;
  species: string;
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
    imgId: item.imgId,       // ? camelCase from Pydantic alias
    species: item.species,
  }));
}

export { searchDatabase };