import { SpeciesImageUmap } from "./speciesData";

const TILE_LAYER_URL =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

const SECONDARY_TILE_LAYER_URL =
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const TILE_LAYER_ATTRIBUTION_URL =
  '&copy; <a href="https://carto.com/" target="_blank">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

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

export interface UmapOccurrence {
  key: string | number;
  decimalLatitude: number;
  decimalLongitude: number;
  classDv: string;
  cluster: number;
}

function getTileLayerUrl(): string {
  return TILE_LAYER_URL;
}

function getTileLayerAttributionUrl(): string {
  return TILE_LAYER_ATTRIBUTION_URL;
}

function getClusterColor(): string[] {
  return CLUSTER_COLORS;
}

async function fetchGbifOccurrences(
  scientificName: string
): Promise<Occurrence[]> {
  // Basic check for valid name format
  if (!scientificName || !scientificName.includes(" ")) {
    console.warn(`Invalid scientific name for GBIF lookup: ${scientificName}`);
    return [];
  }

  try {
    const response = await fetch(
      `/api/gbif-occurrences?species=${encodeURIComponent(scientificName.trim())}`
    );

    if (!response.ok) {
      throw new Error(
        `GBIF API error: ${response.status} ${response.statusText}`
      );
    }

    const data = await response.json();

    // Process results: Filter out occurrences without valid lat/lon
    interface GbifRawOccurrence {
      key: string | number;
      decimalLatitude: number;
      decimalLongitude: number;
    }

    const occurrences = data.results
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

    console.log(
      `Fetched ${occurrences.length} valid GBIF occurrences for ${scientificName}`
    );
    return occurrences;
  } catch (error) {
    console.error(
      `Error fetching GBIF occurrences for ${scientificName}:`,
      error
    );
    return [];
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
  getTileLayerUrl,
  getTileLayerAttributionUrl,
  parseUmapCoordinates,
  getClusterColor,
};
