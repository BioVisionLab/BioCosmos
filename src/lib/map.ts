import type { StyleSpecification } from "maplibre-gl";

// OpenFreeMap serves MapLibre vector styles for free, without an API key.
const BASEMAP_STYLE_LIGHT = "https://tiles.openfreemap.org/styles/positron";
const BASEMAP_STYLE_DARK = "https://tiles.openfreemap.org/styles/dark";

// The styles carry their own OpenMapTiles/OpenStreetMap credit, so this only
// adds the (optional, but appreciated) OpenFreeMap link on top of it.
const BASEMAP_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a>';

/**
 * Why a map has no GBIF layer.
 *
 * GBIF has no georeferenced records, GBIF does not know the name at all, or
 * the request failed. A reader can act on the difference, so the UI is told
 * which it is.
 */
export type GbifLookupStatus = "ok" | "unmatched" | "error";

export interface GbifTaxonResult {
  status: GbifLookupStatus;
  /** The GBIF backbone key the density tiles are drawn for. */
  taxonKey?: number;
  /** Georeferenced records without a geospatial issue. */
  count?: number;
  /** The name GBIF matched, when it matched one. */
  matchedName?: string;
}

/** The specimen record a map point stands for, as its popup shows it. */
export interface SpecimenRecord {
  imgId: string;
  catalogNumber: string | null;
  institutionCode: string | null;
  institutionName: string | null;
  sourceDb: string | null;
  /** The views photographed, e.g. ["dorsal", "ventral"]. */
  sides: string[];
  validationStatus: string | null;
  /** The locality as the record states it: what the coordinate was checked against. */
  recordedCountry: string | null;
  recordedAdm1: string | null;
  /** The GADM region the coordinate falls in. */
  referenceCountry: string | null;
  referenceAdm1: string | null;
}

/** One georeferenced specimen from our own collection. */
export interface SpeciesCoordinatePoint {
  /** The representative image: dorsal when the specimen has one. */
  imgId: string;
  lat: number;
  lon: number;
  /** Images of this specimen, all sharing the coordinate. */
  imageCount: number;
  /** The views photographed, e.g. ["dorsal", "ventral"]. */
  sides: string[];
  sourceDb: string | null;
  sex: string | null;
  /** The specimen's catalog number at its holding institution. */
  catalogNumber: string | null;
  institutionCode: string | null;
  /** The holder's full name, when its code could be resolved. */
  institutionName: string | null;
  /** GADM validation status, or null when validation has not been run. */
  validationStatus: string | null;
  recordedCountry: string | null;
  recordedAdm1: string | null;
  referenceCountry: string | null;
  referenceAdm1: string | null;
}

export interface SpeciesCoordinates {
  /** Specimens with a usable coordinate, before any cap. */
  total: number;
  truncated: boolean;
  points: SpeciesCoordinatePoint[];
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

const GBIF_DENSITY_TILE_URL =
  "https://api.gbif.org/v2/map/occurrence/density/{z}/{x}/{y}@1x.png";

/**
 * The GBIF Maps API density layer for a taxon.
 *
 * Every georeferenced record GBIF holds, pre-aggregated into hexagons, so the
 * whole range is drawn at any zoom for the cost of a few tiles — rather than
 * the first page of the occurrence search, which showed whichever 200 records
 * GBIF happened to return first. The hexagons shrink as the map zooms in.
 *
 * The style ramps from hot pink to deep plum, so the darkest hexagons are the
 * densest. `purpleYellow` ran the other way (densest was the palest), and the
 * `colors` parameter is ignored by the PNG density tiles. The pink/plum hues
 * also stay clear of the green and orange specimen markers drawn on top.
 */
function gbifDensityTileUrl(taxonKey: number): string {
  const params = new URLSearchParams({
    taxonKey: String(taxonKey),
    srs: "EPSG:3857",
    bin: "hex",
    hexPerTile: "40",
    style: "iNaturalist.poly",
  });
  return `${GBIF_DENSITY_TILE_URL}?${params.toString()}`;
}

const GBIF_ATTRIBUTION =
  '<a href="https://www.gbif.org" target="_blank">GBIF</a>';

/**
 * Resolve a species to its GBIF taxon and record count.
 *
 * `recordedName` is what the collection calls the taxon and may be a URL slug
 * (`danaus_plexippus`); `acceptedName` is what Catalogue of Life resolved it
 * to. The route tries the accepted name first and un-slugs either.
 */
async function fetchGbifTaxon(
  recordedName: string,
  acceptedName?: string | null,
): Promise<GbifTaxonResult> {
  if (!recordedName || !recordedName.trim()) {
    return { status: "unmatched" };
  }

  const params = new URLSearchParams({ species: recordedName.trim() });
  if (acceptedName && acceptedName.trim()) {
    params.set("accepted", acceptedName.trim());
  }

  try {
    const response = await fetch(`/api/gbif-taxon?${params.toString()}`);
    const data = await response.json();
    if (!response.ok || data.status === "error") {
      return { status: "error" };
    }
    if (data.status !== "ok" || typeof data.taxonKey !== "number") {
      return { status: "unmatched" };
    }
    return {
      status: "ok",
      taxonKey: data.taxonKey,
      count: typeof data.count === "number" ? data.count : undefined,
      matchedName: data.matchedName,
    };
  } catch (error) {
    console.error(`Error resolving GBIF taxon for ${recordedName}:`, error);
    return { status: "error" };
  }
}

/**
 * The georeferenced specimens of a species in our own collection.
 *
 * Keyed on the recorded name, like every other occurrence lookup. Null when
 * the request failed, so the card can tell an error from a species with no
 * coordinates.
 */
async function fetchSpeciesCoordinates(
  species: string,
): Promise<SpeciesCoordinates | null> {
  if (!species || !species.trim()) {
    return { total: 0, truncated: false, points: [] };
  }
  try {
    const response = await fetch(
      `/api/species-coordinates?species=${encodeURIComponent(species.trim())}`,
    );
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    const points: SpeciesCoordinatePoint[] = (data.points ?? []).filter(
      (point: SpeciesCoordinatePoint) =>
        Number.isFinite(point.lat) && Number.isFinite(point.lon),
    );
    return {
      total: typeof data.total === "number" ? data.total : points.length,
      truncated: !!data.truncated,
      points,
    };
  } catch (error) {
    console.error(`Error fetching coordinates for ${species}:`, error);
    return null;
  }
}

export {
  GBIF_ATTRIBUTION,
  fetchGbifTaxon,
  fetchSpeciesCoordinates,
  gbifDensityTileUrl,
  getBasemapStyleUrl,
  getBasemapAttribution,
  loadLightBasemapStyle,
};
