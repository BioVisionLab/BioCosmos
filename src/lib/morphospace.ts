/**
 * Dorso-ventral morphospaces of the UNICOM image embeddings.
 *
 * Precomputed offline by `packages/morphospace` and served by the backend's
 * `/morphospace` endpoints. Fetched in the browser through the
 * `/api/morphospace` proxy, and only once a section scrolls into view: a
 * family's payload is several hundred kilobytes, which has no business in a
 * page's first render.
 */

export type MorphospaceRank = "all" | "family" | "genus";
export type Side = "dorsal" | "ventral";
export const SIDES: Side[] = ["dorsal", "ventral"];

export interface Integration {
  /** Species seen from both sides. */
  n: number | null;
  /** Mantel r between the dorsal and ventral distance matrices. */
  r: number | null;
  p: number | null;
}

export interface SideDisparity {
  nSpecies: number;
  sumVar: number | null;
  rarefiedMean: number | null;
  rarefiedLow: number | null;
  rarefiedHigh: number | null;
  rarefyK: number;
}

export type Disparity = Partial<Record<Side, SideDisparity>>;

export interface ScopeSummary {
  rank: MorphospaceRank;
  key: string;
  name: string;
  parentFamily: string | null;
  nSpecies: number;
  nSpeciesBoth: number;
  basis: "both_sides" | "all_centroids";
  /** Share of variance on PC1..PC3. */
  explained: [number, number, number];
  integration: Integration;
  runId: string;
}

/** One entry per species and side, column-wise. */
export interface MorphospacePoints {
  species: string[];
  pageKey: (string | null)[];
  genus: (string | null)[];
  side: Side[];
  nImages: number[];
  pc1: number[];
  pc2: number[];
  pc3: number[];
  ellX: (number | null)[];
  ellY: (number | null)[];
  ellSx: (number | null)[];
  ellSy: (number | null)[];
  ellRho: (number | null)[];
  imgId: (string | null)[];
}

export interface AxisExtreme {
  axis: "pc1" | "pc2" | "pc3";
  end: "min" | "max";
  species: string;
  pageKey: string | null;
  side: Side;
  imgId: string | null;
  value: number;
}

export interface ScopeMorphospace {
  scope: ScopeSummary;
  disparity: Disparity;
  points: MorphospacePoints;
  extremes: AxisExtreme[];
  /** A family's genera, for comparing their disparity. */
  children: (ScopeSummary & { disparity: Disparity })[];
}

export interface ScopeRef {
  key: string;
  name: string | null;
  available: boolean;
  nSpecies: number | null;
}

export interface SpeciesSide {
  nImages: number;
  /** Mean cosine distance of the species' images to their centroid. */
  dispersion: number | null;
  imgId: string | null;
  /** Rank among species of the genus / family measured on the same side, 0..1. */
  percentile: { genus: number | null; family: number | null };
}

export interface SpeciesMorphospace {
  species: string;
  pageKey: string | null;
  genus: ScopeRef | null;
  family: ScopeRef | null;
  sides: Record<Side, SpeciesSide | null>;
  dvDivergence: number | null;
  dvDivergencePercentile: { genus: number | null; family: number | null };
}

async function getJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`/api/morphospace/${path}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Morphospace request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchScopeMorphospace(
  rank: MorphospaceRank,
  name: string,
): Promise<ScopeMorphospace | null> {
  const key = rank === "all" ? "all" : name.trim().toLowerCase();
  return getJson(`${rank}/${encodeURIComponent(key)}`);
}

export function fetchSpeciesMorphospace(
  species: string,
): Promise<SpeciesMorphospace | null> {
  return getJson(`species/${encodeURIComponent(species)}`);
}

export function formatPercent(value: number | null | undefined, digits = 0) {
  return value == null ? "–" : `${(value * 100).toFixed(digits)}%`;
}
