export interface DbResultItems {
  species: string;
  matched_fields: string[];
  score: number;
}

export interface SpecimenMetadata {
  img_id: string;
  species: string;
  family: string;
  common_name: string | null;
  sex: string | null;
  life_stage: string | null;
  class_dv: string | null;
  lat: number | null;
  lon: number | null;
  source_db: string | null;
  kingdom: string | null;
  phylum: string | null;
  class: string | null;
  order: string | null;
  matched_fields: string[];
}

export interface DbSearchResponse {
  results: DbResultItems[];
  specimens: SpecimenMetadata[];
}

async function searchDatabase(
  query: string,
  field: string = "all",
): Promise<DbSearchResponse> {
  const response = await fetch(
    `/api/db-search?q=${encodeURIComponent(query)}&field=${encodeURIComponent(field)}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(
      `Database search request failed with status ${response.status}`,
    );
  }

  const json = await response.json();

  const results = (json.results || []).map((item: any) => ({
    matched_fields: item.matched_fields || [],
    score: item.score || 0,
    species: item.species || "",
  }));

  const specimens = (json.specimens || []).map((item: any) => ({
    img_id: item.img_id || "",
    species: item.species || "",
    family: item.family || "",
    common_name: item.common_name,
    sex: item.sex,
    life_stage: item.life_stage,
    class_dv: item.class_dv,
    lat: item.lat,
    lon: item.lon,
    source_db: item.source_db,
    kingdom: item.kingdom,
    phylum: item.phylum,
    class: item.class,
    order: item.order,
    matched_fields: item.matched_fields || [],
  }));

  return { results, specimens };
}

export { searchDatabase };