/**
 * Species nomenclature, name usages and type material.
 *
 * Served by the backend (`/species/{name}/taxonomy`) from the Catalogue of Life
 * release it ingests, alongside the classification the species page already
 * holds.
 */

export interface ColReference {
  citation: string;
  year: number | null;
  doi: string | null;
  link: string | null;
}

export interface NameUsage {
  colId: string | null;
  name: string;
  authorship: string | null;
  rank: string | null;
  status: string;
  isAccepted: boolean;
  /** The original combination the accepted name is based on. */
  isBasionym: boolean;
  /** The name the collection recorded, when CoL does not list it. */
  isRecorded: boolean;
  nameStatus: string | null;
  publishedIn: ColReference | null;
  publishedInPage: string | null;
  year: number | null;
}

export interface TypeSpecimen {
  status: string;
  typifiedName: string | null;
  citation: string | null;
  institutionCode: string | null;
  catalogNumber: string | null;
  sex: string | null;
  country: string | null;
  locality: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude: string | null;
  collector: string | null;
  date: string | null;
  host: string | null;
  link: string | null;
  remarks: string | null;
  reference: ColReference | null;
  referencePage: string | null;
}

export interface Nomenclature {
  acceptedName: string;
  authorship: string | null;
  nameStatus: string | null;
  originalCombination: string | null;
  originalAuthorship: string | null;
  /** Null when CoL cannot say: a recombined name with no basionym linked. */
  isOriginalCombination: boolean | null;
  originalPublication: ColReference | null;
  originalPublicationPage: string | null;
  year: number | null;
}

export interface TaxonomyDetail {
  nomenclature: Nomenclature;
  nameUsages: NameUsage[];
  typeMaterial: TypeSpecimen[];
  /** False when the backend has not ingested type material or references. */
  detailAvailable: boolean;
}

/**
 * Fetch the taxonomy detail of a species.
 *
 * Resolves to null when the name does not resolve to a CoL species; rejects
 * when the request itself fails, so the caller can tell the two apart.
 */
export async function fetchTaxonomyDetail(
  species: string,
): Promise<TaxonomyDetail | null> {
  const response = await fetch(
    `/api/taxonomy/species?species=${encodeURIComponent(species)}`,
    { headers: { Accept: "application/json" } },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  return {
    nomenclature: data.nomenclature,
    nameUsages: Array.isArray(data.nameUsages) ? data.nameUsages : [],
    typeMaterial: Array.isArray(data.typeMaterial) ? data.typeMaterial : [],
    detailAvailable: data.detailAvailable !== false,
  };
}

/** The name-bearing types; everything else belongs to the type series. */
export const PRIMARY_TYPE_STATUSES: ReadonlySet<string> = new Set([
  "holotype",
  "neotype",
  "lectotype",
  "syntype",
]);
