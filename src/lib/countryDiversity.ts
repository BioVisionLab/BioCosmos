import { API_HOST } from "@/lib/config";

/**
 * Species diversity by validated country, from `/stats/country`.
 *
 * The backend normalizes GADM codes to ISO 3166-1 alpha-2 with the same
 * harmonize-core lookup the data summary notebook uses, and supplies the
 * display name, so the map, the tables and the published figure agree on
 * both the code and the name of every country.
 */
export interface CountryDiversityRow {
  countryCode: string;
  countryName: string;
  speciesCount: number;
  imageCount: number;
  /** Images whose country was imputed from the coordinate alone. */
  imputedImageCount: number;
}

export interface CountryDiversity {
  countries: CountryDiversityRow[];
  mappedImages: number;
  imputedImages: number;
  unresolvedImages: number;
}

export interface CountrySpeciesRow {
  species: string;
  imageCount: number;
  imputedImageCount: number;
}

export interface CountrySpecies {
  countryCode: string;
  countryName: string;
  species: CountrySpeciesRow[];
}

/** An ISO 3166-1 alpha-2 code, in any case. */
export function isAlpha2(value: string): boolean {
  return /^[A-Za-z]{2}$/.test(value);
}

export function countryHref(code: string): string {
  return `/collections/country/${code.toLowerCase()}`;
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_HOST}${path}`, {
      // The numbers only change when the coordinate validation or taxonomy is
      // rebuilt; the backend sends a one-day Cache-Control to match.
      next: { revalidate: 3600 },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/** Server-side only: reads API_HOST. */
export function fetchCountryDiversity(): Promise<CountryDiversity | null> {
  return fetchJson<CountryDiversity>("/stats/country");
}

/** Server-side only: reads API_HOST. */
export function fetchCountrySpecies(
  code: string,
): Promise<CountrySpecies | null> {
  if (!isAlpha2(code)) return Promise.resolve(null);
  return fetchJson<CountrySpecies>(`/stats/country/${code.toUpperCase()}`);
}
