"use client";

// Render the UMAP cluster distribution over an OpenFreeMap basemap.
import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import Image from "next/image";
import PointMap, { MapPoint } from "@/components/map/PointMap";
import { UmapOccurrence } from "@/lib/map";
import { fetchThumbnailById } from "@/lib/images";
import { ImageLoading } from "@/components/Loadings";
import { toTitleCase } from "@/lib/textUtils";

const MAP_IMAGE_SIZE = 120;
const CIRCLE_RADIUS = 7;

interface ClusterPoint extends MapPoint {
  cluster: number;
  classDv: string;
}

function MapImage({ imgId }: { imgId: string }) {
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchImageUrl = async () => {
      try {
        const url = await fetchThumbnailById(imgId);
        setImgUrl(url);
      } catch (err) {
        console.error("Error fetching cluster image:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchImageUrl();
  }, [imgId]);

  if (!imgUrl) {
    return <ImageLoading size={MAP_IMAGE_SIZE} />;
  }

  if (loading) {
    return <ImageLoading size={MAP_IMAGE_SIZE} />;
  }

  return (
    <div className="flex items-center justify-center">
      <div
        style={{
          position: "relative",
          width: MAP_IMAGE_SIZE,
          height: MAP_IMAGE_SIZE,
        }}
      >
        <Image
          src={imgUrl}
          alt={`Cluster ${imgId}`}
          fill
          className="object-contain"
          unoptimized
        />
      </div>
    </div>
  );
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
        renderPopup={(point) => {
          const cluster = point as ClusterPoint;
          return (
            <div>
              <MapImage imgId={cluster.id.toString()} />
              <p className="font-semibold">Cluster {cluster.cluster}</p>
              <p>{toTitleCase(cluster.classDv)}</p>
              <p>
                Lat: {cluster.lat.toFixed(4)} <br />
                Lon: {cluster.lon.toFixed(4)}
              </p>
            </div>
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
