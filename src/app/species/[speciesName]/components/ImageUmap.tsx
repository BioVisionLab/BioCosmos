import { ImageLoading } from "@/components/Loadings";
import Tips from "@/components/Tips";
import { fetchThumbnailById } from "@/lib/images";
import { fetchSpeciesImageUmap, SpeciesImageUmap } from "@/lib/speciesData";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  Cell,
} from "recharts";
import { getClusterColor, parseUmapCoordinates } from "@/lib/map";
import dynamic from "next/dynamic";
import { NoData } from "@/components/NoData";
import { No } from "zod/v4/locales";

const TOOLTIP_IMAGE_SIZE = 80;
const CLUSTER_IMAGE_SIZE = 60;

const UmapClusterDistribution = dynamic(
  () => import("./UmapClusterDistribution"),
  {
    ssr: false,
    loading: () => (
      <div>
        <NoData text="Loading UMAP data..." />
      </div>
    ),
  }
);

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
        <NoData text="Loading UMAP data..." />
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

  const umapOccurrences = parseUmapCoordinates(umapCoords);

  return (
    <div className="p-4 border border-gray-300 dark:border-gray-700 rounded-xl max-w-full h-fit">
      <UmapHeader />
      <div className="grid md:grid-cols-2 gap-4">
        <UmapScatterPlot
          umapCoords={umapCoords}
          clusterColors={getClusterColor()}
        />
        <div className="h-[500px]">
          <UmapClusterDistribution
            occurrences={umapOccurrences}
            clusterColors={getClusterColor()}
          />
        </div>
      </div>
    </div>
  );
}

function UmapScatterPlot({
  umapCoords,
  clusterColors,
}: {
  umapCoords: any[];
  clusterColors: string[];
}) {
  // 1. Calculate Bounds and Prepare Data (Memoized for performance)
  const { processedData, xDomain, yDomain } = useMemo(() => {
    const xValues = umapCoords.map((p) => p.umapX);
    const yValues = umapCoords.map((p) => p.umapY);

    // Group by cluster to find representative points (first occurrence)
    const clusterReps = new Map();
    umapCoords.forEach((p) => {
      const cluster = p.clusterLabel ?? -1;
      if (!clusterReps.has(cluster)) {
        clusterReps.set(cluster, p.imgId);
      }
    });

    const data = umapCoords.map((point) => {
      const cluster = point.clusterLabel ?? -1;
      return {
        x: point.umapX,
        y: point.umapY,
        imgId: point.imgId,
        cluster: cluster,
        fill: clusterColors[cluster % clusterColors.length],
        isRepresentative: clusterReps.get(cluster) === point.imgId,
      };
    });

    return {
      processedData: data,
      xDomain: [Math.min(...xValues) - 0.6, Math.max(...xValues) + 0.6],
      yDomain: [Math.min(...yValues) - 0.6, Math.max(...yValues) + 0.6],
    };
  }, [umapCoords, clusterColors]);

  // Separate data into two series: background dots and prominent representatives
  const regularPoints = processedData.filter((p) => !p.isRepresentative);
  const repPoints = processedData.filter((p) => p.isRepresentative);

  const formatAxisTick = (value: number) => value.toFixed(2);

  return (
    <div
      id="umap-scatter-plot"
      className="mb-4 w-full h-[500px] bg-transparent p-4 rounded-xl border border-gray-500"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 20, bottom: 40, left: 20 }}>
          <XAxis
            type="number"
            dataKey="x"
            domain={xDomain}
            tickFormatter={formatAxisTick}
            name="UMAP 1"
            stroke="#94a3b8"
            tick={{ fill: "#475569", fontSize: 12 }}
            label={{
              value: "UMAP 1",
              position: "bottom",
              offset: 0,
              fill: "#64748b",
            }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={yDomain}
            tickFormatter={formatAxisTick}
            name="UMAP 2"
            stroke="#94a3b8"
            tick={{ fill: "#475569", fontSize: 12 }}
            label={{
              value: "UMAP 2",
              angle: -90,
              position: "left",
              offset: 0,
              fill: "#64748b",
            }}
          />
          <ZAxis type="number" range={[50, 50]} />

          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              // Ensure we pick the actual hovered item from the payload
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <UmapTooltipImage imgId={data.imgId} cluster={data.cluster} />
                );
              }
              return null;
            }}
          />

          {/* Main Data Layer: High performance, lower opacity */}
          <Scatter name="Species Points" data={regularPoints}>
            {regularPoints.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} fillOpacity={0.6} />
            ))}
          </Scatter>

          {/* Representative Layer: Custom shapes and higher prominence */}
          <Scatter
            name="Cluster Representatives"
            data={repPoints}
            shape={(props: any) => (
              <CustomDot {...props} imgId={props.payload?.imgId} />
            )}
          >
            {repPoints.map((entry, index) => (
              <Cell key={`rep-cell-${index}`} fill={entry.fill} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <div className="flex justify-between items-center text-xs text-slate-500 px-2">
        <span>
          Total samples: <b>{umapCoords.length}</b>
        </span>
        <span>
          Clusters identified:{" "}
          <b>{new Set(umapCoords.map((p) => p.clusterLabel)).size}</b>
        </span>
      </div>
    </div>
  );
}

function UmapHeader() {
  return (
    <div className="mb-4">
      <h1 className="text-2xl font-bold">Image Similarity</h1>
      <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
        Specimen image similarity in a 2D space using UMAP dimensionality
        reduction.
      </p>
      <Tips message="Hover on a point to preview a specimen image; colors show cluster groups" />
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
      <foreignObject
        x={cx - CLUSTER_IMAGE_SIZE / 2}
        y={cy - CLUSTER_IMAGE_SIZE / 2}
        width={CLUSTER_IMAGE_SIZE}
        height={CLUSTER_IMAGE_SIZE}
      >
        <ClusterImage imgId={imgId} />
      </foreignObject>
      <circle cx={cx} cy={cy} r={4} fill={fill} opacity={0.8} />
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

function UmapTooltipImage({
  imgId,
  cluster,
}: {
  imgId: string;
  cluster: number;
}) {
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
      <p className="mt-2 text-center text-sm text-gray-200 dark:text-gray-400">
        Cluster {cluster}
      </p>
    </div>
  );
}

export default ImageUmap;
