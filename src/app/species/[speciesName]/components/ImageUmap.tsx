"use client";
import { ImageLoading } from "@/components/Loadings";
import { fetchThumbnailById } from "@/lib/images";
import { fetchSpeciesImageUmap, SpeciesImageUmap } from "@/lib/speciesData";
import Image from "next/image";
import { useEffect, useState } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from "recharts";

const TOOLTIP_IMAGE_SIZE = 80;
const CLUSTER_IMAGE_SIZE = 24;

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

function ImageUmap({ species }: { species: string }) {
  const [umapCoords, setUmapCoords] = useState<SpeciesImageUmap[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUmapData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSpeciesImageUmap(species);
        if (data) {
          setUmapCoords(data);
        } else {
          setError("No UMAP data found for this species.");
        }
      } catch (err) {
        setError("Error fetching UMAP data.");
      } finally {
        setLoading(false);
      }
    };

    fetchUmapData();
  }, [species]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-lg">Loading UMAP data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 p-4 border border-red-300 rounded">
        Error: {error}
      </div>
    );
  }

  if (!umapCoords || umapCoords.length === 0) {
    return <div className="p-4">No UMAP data available.</div>;
  }

  // Calculate min and max for X and Y axes
  const xValues = umapCoords.map((point) => point.umapX);
  const yValues = umapCoords.map((point) => point.umapY);

  const xMin = Math.min(...xValues) - 0.2;
  const xMax = Math.max(...xValues) + 0.2;
  const yMin = Math.min(...yValues) - 0.2;
  const yMax = Math.max(...yValues) + 0.2;

  // Group data by cluster for separate scatter series
  const clusterGroups = umapCoords.reduce((acc, point) => {
    const cluster = point.clusterLabel ?? -1;
    if (!acc[cluster]) {
      acc[cluster] = [];
    }
    acc[cluster].push({
      x: point.umapX,
      y: point.umapY,
      imgId: point.imgId,
      cluster: cluster,
    });
    return acc;
  }, {} as Record<number, Array<{ x: number; y: number; imgId: string; cluster: number }>>);

  const formatAxisTick = (value: number) => value.toFixed(2);

  const clusters = Object.keys(clusterGroups)
    .map(Number)
    .sort((a, b) => a - b);

  // Mark one representative point per cluster (first point)
  // to display a thumbnail image
  const representativeIds = new Set(
    clusters.map((cluster) => clusterGroups[cluster][0].imgId)
  );

  // Add representative flag to all data points
  const allDataWithReps = umapCoords.map((point) => ({
    x: point.umapX,
    y: point.umapY,
    imgId: point.imgId,
    cluster: point.clusterLabel ?? -1,
    isRepresentative: representativeIds.has(point.imgId),
  }));

  return (
    <div className="p-4 border border-gray-300 dark:border-gray-700 rounded-xl max-w-4xl h-fit">
      <h2 className="text-lg font-semibold">Specimen Similarity Map</h2>
      <p className="mb-4 text-xs text-gray-600 dark:text-gray-400">
        Images with similar visual features clustered using UMAP dimensionality
        reduction. Hover to preview a specimen image; colors show cluster groups
      </p>

      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 20 }}>
          <XAxis
            type="number"
            dataKey="x"
            domain={[xMin, xMax]}
            tickFormatter={formatAxisTick}
            name="UMAP 1"
            label={{ value: "UMAP 1", position: "insideBottom", offset: -10 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[yMin, yMax]}
            tickFormatter={formatAxisTick}
            name="UMAP 2"
            label={{ value: "UMAP 2", angle: -90, position: "insideLeft" }}
          />
          <ZAxis range={[60, 60]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return <UmapTooltipImage imgId={data.imgId} />;
              }
              return null;
            }}
          />

          {clusters.map((cluster) => {
            const regularData = allDataWithReps.filter(
              (point) => point.cluster === cluster && !point.isRepresentative
            );
            return (
              <Scatter
                key={cluster}
                name={`Cluster ${cluster}`}
                data={regularData}
                fill={CLUSTER_COLORS[cluster % CLUSTER_COLORS.length]}
                opacity={0.7}
              />
            );
          })}

          {clusters.map((cluster) => {
            const repData = allDataWithReps.filter(
              (point) => point.cluster === cluster && point.isRepresentative
            );
            return (
              <Scatter
                key={`rep-${cluster}`}
                name={`Cluster ${cluster} Rep`}
                data={repData}
                fill={CLUSTER_COLORS[cluster % CLUSTER_COLORS.length]}
                opacity={1}
                shape={<CustomDot />}
              />
            );
          })}
        </ScatterChart>
      </ResponsiveContainer>

      <div className="mt-4 text-sm text-gray-600">
        Total points: {umapCoords.length} &middot; Clusters: {clusters.length}
      </div>
    </div>
  );
}

const CustomDot = (props: any) => {
  const { cx, cy, fill, isRepresentative, imgId } = props;

  if (!isRepresentative) {
    return <circle cx={cx} cy={cy} r={4} fill={fill} opacity={0.7} />;
  }

  return (
    <g>
      <circle cx={cx} cy={cy} r={4} fill={fill} opacity={0.7} />
      <foreignObject
        x={cx}
        y={cy}
        width={CLUSTER_IMAGE_SIZE}
        height={CLUSTER_IMAGE_SIZE}
      >
        <ClusterImage imgId={imgId} />
      </foreignObject>
    </g>
  );
};

function ClusterImage({ imgId }: { imgId: string }) {
  const [imgUrl, setImgUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchImageUrl = async () => {
      try {
        const url = await fetchThumbnailById(imgId);
        setImgUrl(url);
      } catch (err) {
        console.error("Error fetching cluster image:", err);
      }
    };

    fetchImageUrl();
  }, [imgId]);

  if (!imgUrl) {
    return <ImageLoading size={CLUSTER_IMAGE_SIZE} />;
  }

  return (
    <Image
      src={imgUrl}
      alt={`Cluster ${imgId}`}
      width={CLUSTER_IMAGE_SIZE}
      height={CLUSTER_IMAGE_SIZE}
    />
  );
}

function UmapTooltipImage({ imgId }: { imgId: string }) {
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchImageUrl = async () => {
      setLoading(true);
      setError(null);
      try {
        const imgUrl = await fetchThumbnailById(imgId);
        setImgUrl(imgUrl);
      } catch (err) {
        setError("Error fetching image.");
      } finally {
        setLoading(false);
      }
    };

    fetchImageUrl();
  }, [imgId]);

  if (loading) {
    return <ImageLoading size={TOOLTIP_IMAGE_SIZE} />;
  }

  if (error) {
    return <div className="text-red-500">Error: {error}</div>;
  }

  if (!imgUrl) {
    return <div>No image available.</div>;
  }

  return (
    <div className="p-2 border border-emerald-500 bg-gray-200 dark:bg-gray-700 rounded-lg shadow">
      <Image
        src={imgUrl}
        alt={`Specimen ${imgId}`}
        width={80}
        height={80}
        className="rounded border"
      />
    </div>
  );
}

export default ImageUmap;
