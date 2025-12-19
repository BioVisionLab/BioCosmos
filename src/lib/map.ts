import { SpeciesImageUmap } from "./speciesData";

const TILE_LAYER_URL =
  "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png";

const SECONDARY_TILE_LAYER_URL =
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const TILE_LAYER_ATTRIBUTION_URL =
  '&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

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

  // Construct the GBIF API URL (limit to 200 results for performance)
  // Using hasCoordinate=true and hasGeospatialIssue=false for cleaner data
  const gbifLimit = 200;
  const gbifApiUrl = `https://api.gbif.org/v1/occurrence/search?scientificName=${encodeURIComponent(
    scientificName
  )}&limit=${gbifLimit}&hasCoordinate=true&hasGeospatialIssue=false`;

  console.log(`Fetching GBIF data from: ${gbifApiUrl}`); // Log the URL for debugging

  try {
    const response = await fetch(gbifApiUrl, {
      // Optional: Add cache control if needed, but default Next.js fetch caching is usually sufficient
      // next: { revalidate: 3600 * 24 } // Example: revalidate once per day
    });

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
        key: occ.key, // GBIF unique key for the occurrence
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
    return []; // Return empty array on error
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
