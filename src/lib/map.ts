import type { StyleSpecification } from "maplibre-gl";
import { SpeciesImageUmap } from "./speciesData";

// OpenFreeMap serves MapLibre vector styles for free, without an API key.
const BASEMAP_STYLE_LIGHT = "https://tiles.openfreemap.org/styles/positron";
const BASEMAP_STYLE_DARK = "https://tiles.openfreemap.org/styles/dark";

// The styles carry their own OpenMapTiles/OpenStreetMap credit, so this only
// adds the (optional, but appreciated) OpenFreeMap link on top of it.
const BASEMAP_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a>';

const CLUSTER_COLORS = [
  "#7c3aed", // Purple
  "#2563eb", // Blue
  "#059669", // Green
  "#ea580c", // Orange
  "#dc2626", // Red
  "#db2777", // Pink
  "#0d9488", // Teal
  "#a855f7", // Violet
  "#8b5cf6", // Light Purple
  "#3b82f6", // Light Blue
  "#10b981", // Emerald
  "#f59e0b", // Amber
  "#ef4444", // Light Red
  "#ec4899", // Hot Pink
  "#14b8a6", // Cyan
  "#c084fc", // Lavender
  "#6366f1", // Indigo
  "#06b6d4", // Sky Blue
  "#22c55e", // Lime Green
  "#f97316", // Orange-Red
  "#f43f5e", // Rose
  "#a21caf", // Fuchsia
  "#0891b2", // Dark Cyan
  "#d946ef", // Magenta
];

export interface Occurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  // Add other fields you might fetch from GBIF later, e.g., eventDate, basisOfRecord
}

/**
 * Why a map has no points.
 *
 * Three outcomes that used to be one empty array: GBIF has no georeferenced
 * records, GBIF does not know the name at all, or the request failed. A
 * reader can act on the difference, so the UI is told which it is.
 */
export type GbifLookupStatus = "ok" | "unmatched" | "error";

export interface GbifOccurrenceResult {
  status: GbifLookupStatus;
  occurrences: Occurrence[];
  /** The name GBIF matched, when it matched one. */
  matchedName?: string;
}

export interface UmapOccurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  classDv: string;
  cluster: number;
}

function getBasemapStyleUrl(isDark: boolean): string {
  return isDark ? BASEMAP_STYLE_DARK : BASEMAP_STYLE_LIGHT;
}

/**
 * Layers a thematic world map keeps from the OpenFreeMap style: the sea, the
 * ice caps and the country borders. Everything else — roads, buildings,
 * land use, and every label — is detail that competes with the data and
 * costs requests, so it goes.
 */
const LIGHT_BASEMAP_LAYERS = new Set([
  "background",
  "water",
  "landcover_ice_shelf",
  "landcover_glacier",
]);
// Sub-national lines: state borders are noise at a country scale.
const DROPPED_BOUNDARY_LAYERS = new Set(["boundary_3", "boundary_state"]);

const lightBasemapCache = new Map<boolean, Promise<StyleSpecification>>();

/**
 * The OpenFreeMap style reduced to a light world basemap.
 *
 * Dropping every symbol layer is what lets `glyphs` and `sprite` go too, so
 * the map makes no font or sprite requests at all. Only the vector source the
 * kept layers read survives; the shaded-relief raster source is removed.
 * Fetched once per theme and shared by every map on the page.
 */
function loadLightBasemapStyle(isDark: boolean): Promise<StyleSpecification> {
  const cached = lightBasemapCache.get(isDark);
  if (cached) return cached;

  const promise = fetch(getBasemapStyleUrl(isDark))
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Basemap style request failed: ${response.status}`);
      }
      return response.json() as Promise<StyleSpecification>;
    })
    .then((style) => {
      const layers = style.layers.filter(
        (layer) =>
          LIGHT_BASEMAP_LAYERS.has(layer.id) ||
          ("source-layer" in layer &&
            layer["source-layer"] === "boundary" &&
            !DROPPED_BOUNDARY_LAYERS.has(layer.id)),
      );
      const used = new Set(
        layers.flatMap((layer) => ("source" in layer ? [layer.source] : [])),
      );
      const sources = Object.fromEntries(
        Object.entries(style.sources).filter(([id]) => used.has(id)),
      );
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { glyphs, sprite, ...rest } = style;
      return { ...rest, sources, layers } as StyleSpecification;
    })
    .catch((error) => {
      // Let a later mount retry instead of caching the failure.
      lightBasemapCache.delete(isDark);
      throw error;
    });

  lightBasemapCache.set(isDark, promise);
  return promise;
}

function getBasemapAttribution(): string {
  return BASEMAP_ATTRIBUTION;
}

function getClusterColor(): string[] {
  return CLUSTER_COLORS;
}

/**
 * Fetch the GBIF occurrences for a species.
 *
 * `recordedName` is what the collection calls the taxon and may be a URL slug
 * (`danaus_plexippus`); `acceptedName` is what Catalogue of Life resolved it
 * to. The route tries the accepted name first and un-slugs either, so no
 * cleaning is needed here — and no name is rejected before it is asked about,
 * which is what previously kept the map empty for every species.
 */
async function fetchGbifOccurrences(
  recordedName: string,
  acceptedName?: string | null
): Promise<GbifOccurrenceResult> {
  if (!recordedName || !recordedName.trim()) {
    return { status: "unmatched", occurrences: [] };
  }

  const params = new URLSearchParams({ species: recordedName.trim() });
  if (acceptedName && acceptedName.trim()) {
    params.set("accepted", acceptedName.trim());
  }

  try {
    const response = await fetch(`/api/gbif-occurrences?${params.toString()}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        `GBIF API error: ${response.status} ${response.statusText}`
      );
    }

    if (data.status !== "ok") {
      return { status: data.status === "error" ? "error" : "unmatched", occurrences: [] };
    }

    // Process results: Filter out occurrences without valid lat/lon
    interface GbifRawOccurrence {
      key: string | number;
      decimalLatitude: number;
      decimalLongitude: number;
    }

    const occurrences: Occurrence[] = (data.results ?? [])
      .map((occ: GbifRawOccurrence) => ({
        key: occ.key,
        decimalLatitude: occ.decimalLatitude,
        decimalLongitude: occ.decimalLongitude,
      }))
      .filter(
        (occ: Occurrence) =>
          typeof occ.decimalLatitude === "number" &&
          typeof occ.decimalLongitude === "number" &&
          !isNaN(occ.decimalLatitude) &&
          !isNaN(occ.decimalLongitude)
      );

    return { status: "ok", occurrences, matchedName: data.matchedName };
  } catch (error) {
    console.error(
      `Error fetching GBIF occurrences for ${recordedName}:`,
      error
    );
    return { status: "error", occurrences: [] };
  }
}

function parseUmapCoordinates(umapData: SpeciesImageUmap[]): UmapOccurrence[] {
  // Return nothing if the coordinates are invalid
  if (!umapData || umapData.length === 0) {
    return [];
  }
  // Filter out any umapData entries with invalid coordinates
  const validUmapData = umapData.filter(
    (umap) =>
      typeof umap.lat === "number" &&
      typeof umap.lon === "number" &&
      !isNaN(umap.lat) &&
      !isNaN(umap.lon)
  );
  if (validUmapData.length === 0) {
    return [];
  }

  return validUmapData.map((umap) => ({
    key: umap.imgId,
    decimalLatitude: umap.lat,
    decimalLongitude: umap.lon,
    classDv: umap.classDv ?? "Unknown",
    cluster: umap.clusterLabel ?? -1,
  }));
}

export {
  fetchGbifOccurrences,
  getBasemapStyleUrl,
  getBasemapAttribution,
  loadLightBasemapStyle,
  parseUmapCoordinates,
  getClusterColor,
};
