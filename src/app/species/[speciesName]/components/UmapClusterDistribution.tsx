"use client";

// Render the UMAP cluster distribution over an OpenFreeMap basemap.
import { useMemo } from "react";
import { useTheme } from "next-themes";
import PointMap, { MapPoint } from "@/components/map/PointMap";
import { SpecimenRecordCard } from "@/components/map/SpecimenRecordCard";
import { SpecimenRecord, UmapOccurrence } from "@/lib/map";

const CIRCLE_RADIUS = 7;

interface ClusterPoint extends MapPoint {
  cluster: number;
  classDv: string;
}

export default function UmapClusterDistribution({
  occurrences,
  clusterColors,
}: {
  occurrences: UmapOccurrence[];
  clusterColors: string[];
}): React.ReactElement {
  const { resolvedTheme } = useTheme();
  const isDarkTheme = resolvedTheme === "dark";

  const points = useMemo<ClusterPoint[]>(
    () =>
      occurrences
        .filter(
          (occ) =>
            typeof occ.decimalLatitude === "number" &&
            typeof occ.decimalLongitude === "number" &&
            !Number.isNaN(occ.decimalLatitude) &&
            !Number.isNaN(occ.decimalLongitude),
        )
        .map((occ) => ({
          id: occ.key,
          lat: occ.decimalLatitude,
          lon: occ.decimalLongitude,
          color: clusterColors[occ.cluster % clusterColors.length],
          cluster: occ.cluster,
          classDv: occ.classDv,
        })),
    [occurrences, clusterColors],
  );

  // MapLibre flattens point properties, so the record is looked up by id
  // rather than carried on the point.
  const records = useMemo(
    () =>
      new Map<string, SpecimenRecord>(
        occurrences.map((occ) => [String(occ.key), occ.record]),
      ),
    [occurrences],
  );

  const mapCenter: [number, number] =
    points.length > 0 ? [points[0].lon, points[0].lat] : [0, 20];

  const mapZoom = points.length > 0 ? 4 : 2;

  if (occurrences.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-deep-mocha-500 rounded-xl border border-deep-mocha-500">
        No geographic distribution data available.
      </div>
    );
  }

  return (
    <div
      className={isDarkTheme ? "umap-dark-map" : ""}
      style={{ height: "100%", width: "100%" }}
    >
      <PointMap
        points={points}
        circleRadius={CIRCLE_RADIUS}
        center={mapCenter}
        zoom={mapZoom}
        minZoom={2}
        maxZoom={19}
        interaction="hover"
        popupClassName="species-map-popup"
        renderPopup={(point) => {
          const cluster = point as ClusterPoint;
          const record = records.get(String(cluster.id));
          if (!record) return null;
          return (
            <SpecimenRecordCard
              record={record}
              compact
              leadingRows={[
                [
                  "Cluster",
                  <span key="cluster" className="flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: cluster.color }}
                    />
                    {cluster.cluster}
                  </span>,
                ],
              ]}
            />
          );
        }}
        style={{
          height: "100%",
          width: "100%",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      />
    </div>
  );
}
