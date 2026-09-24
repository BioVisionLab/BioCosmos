export interface DbResultItems {
  species: string;
  /** The species page this entry links to; null when there is none. */
  species_key: string | null;
  matched_fields: string[];
  score: number;
}

export interface SpecimenMetadata {
  img_id: string;
  species: string;
  /**
   * The species page this record links to, chosen by the backend. Null when
   * the record resolves to no species with a page; the row is still listed.
   */
  species_key: string | null;
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

  // The written locality, joined from the GBIF occurrence record. All null
  // for the occurrences with no GBIF record, and until the locality table has
  // been built.
  country: string | null;
  country_code: string | null;
  state_province: string | null;
  county: string | null;
  municipality: string | null;
  locality: string | null;
  verbatim_locality: string | null;

  // Coordinate validation against GADM. All null until `geoharmonize
  // integrate` has been run.
  /** One of the eight CoordinateValidationStatus codes. */
  validation_status: string | null;
  coordinate_check: string | null;
  country_check: string | null;
  adm1_check: string | null;
  /** Null unless exactly one GADM region matched the coordinate. */
  reference_country: string | null;
  reference_adm1: string | null;

  // Who holds the specimen and how they number it. All null for occurrences
  // with no GBIF record, and until the provenance table has been built. The
  // name and website only when instharmonize resolved the code.
  institution_code: string | null;
  catalog_number: string | null;
  institution_name: string | null;
  institution_homepage: string | null;

  // LepTraits for the record's accepted species, as readable words. All null
  // for species LepTraits lacks, and until the trait index has been built.
  canopy_affinity: string | null;
  edge_affinity: string | null;
  moisture_affinity: string | null;
  disturbance_affinity: string | null;
  voltinism: string | null;
  diapause_stage: string | null;
  oviposition_style: string | null;
  hostplant_families: string | null;
  host_breadth: string | null;
  flight_months: string | null;
  wing_size: string | null;
}

export type TraitField =
  | "canopy_affinity"
  | "edge_affinity"
  | "moisture_affinity"
  | "disturbance_affinity"
  | "voltinism"
  | "diapause_stage"
  | "oviposition_style"
  | "hostplant_families"
  | "host_breadth"
  | "flight_months"
  | "wing_size";

/**
 * The LepTraits fields the text search can target. Kept out of "All Fields"
 * by the backend: each is a small vocabulary shared by every image of a
 * species, so a sweep for "closed" or "Jun" would return most of the site.
 */
export const TRAIT_FIELD_OPTIONS: { value: TraitField; label: string }[] = [
  { value: "canopy_affinity", label: "Canopy (e.g. closed, open)" },
  { value: "edge_affinity", label: "Edge Affinity" },
  { value: "moisture_affinity", label: "Moisture (mesic, xeric)" },
  { value: "disturbance_affinity", label: "Disturbance Affinity" },
  { value: "voltinism", label: "Voltinism (univoltine…)" },
  { value: "diapause_stage", label: "Diapause Stage" },
  { value: "oviposition_style", label: "Oviposition Style" },
  { value: "hostplant_families", label: "Host-Plant Family" },
  { value: "host_breadth", label: "Host Breadth (specialist…)" },
  { value: "flight_months", label: "Flight Month (e.g. Jun)" },
  { value: "wing_size", label: "Wing Size (small, medium, large)" },
];

export function isTraitField(field: string): field is TraitField {
  return TRAIT_FIELD_OPTIONS.some((option) => option.value === field);
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
    species_key: item.species_key ?? null,
  }));

  const specimens = (json.specimens || []).map((item: any) => ({
    img_id: item.img_id || "",
    species: item.species || "",
    species_key: item.species_key ?? null,
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
    country: item.country ?? null,
    country_code: item.country_code ?? null,
    state_province: item.state_province ?? null,
    county: item.county ?? null,
    municipality: item.municipality ?? null,
    locality: item.locality ?? null,
    verbatim_locality: item.verbatim_locality ?? null,
    validation_status: item.validation_status ?? null,
    coordinate_check: item.coordinate_check ?? null,
    country_check: item.country_check ?? null,
    adm1_check: item.adm1_check ?? null,
    reference_country: item.reference_country ?? null,
    reference_adm1: item.reference_adm1 ?? null,
    institution_code: item.institution_code ?? null,
    catalog_number: item.catalog_number ?? null,
    institution_name: item.institution_name ?? null,
    institution_homepage: item.institution_homepage ?? null,
    canopy_affinity: item.canopy_affinity ?? null,
    edge_affinity: item.edge_affinity ?? null,
    moisture_affinity: item.moisture_affinity ?? null,
    disturbance_affinity: item.disturbance_affinity ?? null,
    voltinism: item.voltinism ?? null,
    diapause_stage: item.diapause_stage ?? null,
    oviposition_style: item.oviposition_style ?? null,
    hostplant_families: item.hostplant_families ?? null,
    host_breadth: item.host_breadth ?? null,
    flight_months: item.flight_months ?? null,
    wing_size: item.wing_size ?? null,
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