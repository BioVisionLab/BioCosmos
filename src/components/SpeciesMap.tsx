"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import PointMap, { MapPoint } from "@/components/map/PointMap";
import { Occurrence } from "@/lib/map";

const OCCURRENCE_COLOR = "#10b981";
const CIRCLE_RADIUS = 4;

interface SpeciesMapProps {
  occurrences?: Occurrence[];
}

const SpeciesMap: React.FC<SpeciesMapProps> = ({ occurrences = [] }) => {
  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const points = useMemo<MapPoint[]>(
    () =>
      occurrences
        .filter(
          (occ) =>
            typeof occ.decimalLatitude === "number" &&
            typeof occ.decimalLongitude === "number" &&
            !Number.isNaN(occ.decimalLatitude) &&
            !Number.isNaN(occ.decimalLongitude),
        )
        .map((occ, idx) => ({
          id: `${occ.key || "occ"}-${idx}`,
          lat: occ.decimalLatitude,
          lon: occ.decimalLongitude,
          color: OCCURRENCE_COLOR,
        })),
    [occurrences],
  );

  const mapCenter: [number, number] =
    points.length > 0 ? [points[0].lon, points[0].lat] : [0, 20];

  const mapZoom = points.length > 0 ? 4 : 2;

  return (
    <div
      className={isDarkTheme ? "umap-dark-map" : ""}
      style={{ height: "400px", width: "100%" }}
    >
      <PointMap
        points={points}
        circleRadius={CIRCLE_RADIUS}
        center={mapCenter}
        zoom={mapZoom}
        minZoom={2}
        maxZoom={18}
        interaction="click"
        renderPopup={(point) => (
          <>
            Occurrence Record <br />
            Lat: {point.lat.toFixed(4)} <br />
            Lon: {point.lon.toFixed(4)}
          </>
        )}
        style={{
          height: "400px",
          width: "100%",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      />
    </div>
  );
};

export default SpeciesMap;
