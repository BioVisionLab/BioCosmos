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
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ZAxis,
} from "recharts";

// Define colors for each cluster
const CLUSTER_COLORS = [
  "#8b5cf6", // Purple
  "#3b82f6", // Blue
  "#10b981", // Green
  "#f59e0b", // Orange
  "#ef4444", // Red
  "#ec4899", // Pink
  "#14b8a6", // Teal
  "#f97316", // Orange-Red
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

  const clusters = Object.keys(clusterGroups)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="p-4 border border-gray-300 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-800 max-w-4xl h-fit">
      <h3 className="mb-2 text-xl font-semibold">
        UMAP Embeddings for specimen images
      </h3>
      <p className="text-xs text-gray-600 dark:text-gray-400">
        UMAP visualization of specimen images. Each point represents an image,
        and colors indicate different clusters based on visual similarity.
      </p>
      <p className="mb-4 text-xs text-gray-600 dark:text-gray-400">
        Tips: Hover over points to see specimen thumbnails.
      </p>

      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          {/* <CartesianGrid strokeDasharray="3 3" /> */}
          <XAxis
            type="number"
            dataKey="x"
            name="UMAP 1"
            label={{ value: "UMAP 1", position: "insideBottom", offset: -10 }}
          />
          <YAxis
            type="number"
            dataKey="y"
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
          <Legend
            verticalAlign="bottom"
            wrapperStyle={{
              paddingTop: "24px",
            }}
          />

          {clusters.map((cluster) => (
            <Scatter
              key={cluster}
              name={`Cluster ${cluster}`}
              data={clusterGroups[cluster]}
              fill={CLUSTER_COLORS[cluster % CLUSTER_COLORS.length]}
              opacity={0.7}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>

      <div className="mt-2 text-sm text-gray-600">
        Total points: {umapCoords.length} | Clusters: {clusters.join(", ")}
      </div>
    </div>
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
    return <ImageLoading size={80} />;
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
