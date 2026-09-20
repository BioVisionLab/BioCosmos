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

  // The Catalogue of Life update for this occurrence. All null until a
  // colharmonize run has been loaded.
  /** Accepted binomial, else the genus the match resolved to, else null. */
  display_accepted_name: string | null;
  /** The accepted name at its own rank, which may be a bare genus. */
  accepted_name: string | null;
  accepted_rank: string | null;
  accepted_authorship: string | null;
  accepted_family: string | null;
  /** MATCHED | AMBIGUOUS | UNMATCHED */
  update_status: string | null;
  /** May carry a SUBSPECIES_ or GENUS_ rank-cascade prefix. */
  match_method: string | null;
  candidate_count: number | null;
}

export interface DbSearchResponse {
  results: DbResultItems[];
  specimens: SpecimenMetadata[];
  total_specimens: number;
  page: number;
  limit: number;
}

async function searchDatabase(
  query: string,
  field: string = "all",
  page: number = 1,
): Promise<DbSearchResponse> {
  const response = await fetch(
    `/api/db-search?q=${encodeURIComponent(query)}&field=${encodeURIComponent(field)}&page=${encodeURIComponent(page)}`,
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
    display_accepted_name: item.display_accepted_name ?? null,
    accepted_name: item.accepted_name ?? null,
    accepted_rank: item.accepted_rank ?? null,
    accepted_authorship: item.accepted_authorship ?? null,
    accepted_family: item.accepted_family ?? null,
    update_status: item.update_status ?? null,
    match_method: item.match_method ?? null,
    candidate_count: item.candidate_count ?? null,
  }));

  return {
    results,
    specimens,
    total_specimens: json.total_specimens || 0,
    page: json.page || 1,
    limit: json.limit || 50,
  };
}

export { searchDatabase };