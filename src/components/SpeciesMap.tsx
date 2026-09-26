"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import PointMap, { MapPoint, RasterUnderlay } from "@/components/map/PointMap";
import {
  GBIF_ATTRIBUTION,
  gbifDensityTileUrl,
  SpeciesCoordinatePoint,
} from "@/lib/map";
import { SpecimenRecordCard } from "@/components/map/SpecimenRecordCard";

const MARKER_RADIUS = 6;

/**
 * How a specimen's coordinate fared against GADM, as the map colours it.
 *
 * Three kinds rather than eight codes: a reader scanning a map needs to know
 * whether a dot agrees with the locality its label records, not which check
 * it failed. The popup carries the exact status.
 */
export type MarkerKind = "valid" | "flagged" | "unvalidated";

export const MARKER_COLORS: Record<MarkerKind, string> = {
  valid: "#4f8b41", // hunter-green-600
  flagged: "#d95326", // burnt-peach-500
  unvalidated: "#a29090", // deep-mocha-400
};

export function markerKind(status: string | null | undefined): MarkerKind {
  if (!status) return "unvalidated";
  return status === "VALID" ? "valid" : "flagged";
}

interface SpeciesMapProps {
  /** Our own georeferenced specimens, drawn as markers. */
  points?: SpeciesCoordinatePoint[];
  /** The GBIF taxon whose density tiles are drawn beneath the markers. */
  gbifTaxonKey?: number | null;
}

type Bounds = [[number, number], [number, number]];

/**
 * Where the camera opens.
 *
 * Fit to our specimens when they sit in one part of the world. A species
 * collected on every continent spans the whole globe, where fitting gives a
 * world view centred on 0° that can crop the very region most specimens come
 * from — so past half the globe the map centres on the median specimen
 * instead, at a world zoom. The median, not the mean: a few outliers across
 * the antimeridian would drag a mean into the ocean.
 */
function initialView(points: SpeciesCoordinatePoint[]): {
  bounds: Bounds | null;
  center: [number, number];
} {
  const world: [number, number] = [0, 20];
  if (points.length === 0) return { bounds: null, center: world };
  let west = 180;
  let south = 90;
  let east = -180;
  let north = -90;
  for (const point of points) {
    west = Math.min(west, point.lon);
    east = Math.max(east, point.lon);
    south = Math.min(south, point.lat);
    north = Math.max(north, point.lat);
  }
  if (east - west <= 180) {
    return {
      bounds: [
        [west, south],
        [east, north],
      ],
      center: world,
    };
  }
  const median = (values: number[]) =>
    values.sort((a, b) => a - b)[Math.floor(values.length / 2)];
  return {
    bounds: null,
    center: [
      median(points.map((point) => point.lon)),
      median(points.map((point) => point.lat)),
    ],
  };
}

const SpeciesMap: React.FC<SpeciesMapProps> = ({
  points = [],
  gbifTaxonKey = null,
}) => {
  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const byId = useMemo(
    () => new Map(points.map((point) => [point.imgId, point])),
    [points],
  );

  const mapPoints = useMemo<MapPoint[]>(
    () =>
      points.map((point) => ({
        id: point.imgId,
        lat: point.lat,
        lon: point.lon,
        color: MARKER_COLORS[markerKind(point.validationStatus)],
        radius: MARKER_RADIUS,
        // A dark ring on the light basemap and a light one on the dark: the
        // outline is what sets our specimens apart from the GBIF hexagons
        // underneath, whatever their colour.
        strokeColor: isDarkTheme ? "#ffffff" : "#1c1717",
      })),
    [points, isDarkTheme],
  );

  const underlay = useMemo<RasterUnderlay | null>(
    () =>
      gbifTaxonKey
        ? {
            id: `gbif-${gbifTaxonKey}`,
            tiles: [gbifDensityTileUrl(gbifTaxonKey)],
            attribution: GBIF_ATTRIBUTION,
            opacity: 0.75,
          }
        : null,
    [gbifTaxonKey],
  );

  // Our specimens frame the view when there are any; otherwise the GBIF
  // layer covers the globe, so start from the world.
  const { bounds, center } = useMemo(() => initialView(points), [points]);

  return (
    // Tinted like the loading skeleton, so the moment between the skeleton
    // and the first basemap tiles is the same surface rather than a blank.
    <div
      className={`rounded-b-xl bg-deep-mocha-100/70 dark:bg-deep-mocha-800/60 ${
        isDarkTheme ? "umap-dark-map" : ""
      }`}
      style={{ height: "400px", width: "100%" }}
    >
      <PointMap
        points={mapPoints}
        circleRadius={MARKER_RADIUS}
        center={center}
        zoom={1}
        fitBounds={bounds}
        rasterUnderlay={underlay}
        minZoom={0}
        maxZoom={18}
        interaction="click"
        popupClassName="species-map-popup"
        renderPopup={(mapPoint) => {
          const point = byId.get(String(mapPoint.id));
          if (!point) return null;
          return <SpecimenRecordCard record={point} />;
        }}
        style={{
          height: "400px",
          width: "100%",
          // Bottom corners only: the map is flush to the edges of the card
          // that holds it, so its top meets the info line squarely and its
          // bottom follows the card's own `rounded-xl`.
          borderRadius: "0 0 12px 12px",
          overflow: "hidden",
        }}
      />
    </div>
  );
};

export default SpeciesMap;
