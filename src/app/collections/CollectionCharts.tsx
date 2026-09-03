"use client";

import { useEffect, useMemo, useState } from "react";
import {
  PieChart,
  Pie,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

import { NoData } from "@/components/NoData";
import { fetchEmbeddingStats, type EmbeddingSummary } from "@/lib/metaStats";
import { toSentenceCase, toSpeciesName } from "@/lib/textUtils";

const FAMILY_COLORS = [
  "#3eadc1",
  "#62ad52",
  "#d95326",
  "#8bceda",
  "#a1ce97",
  "#e8987d",
  "#006666",
];

const BAR_GRADIENT_START = "#3eadc1";
const BAR_GRADIENT_END = "#256874";

const EMBEDDING_COLORS: Record<string, string> = {
  CLIP: "#3eadc1", // pacific-blue-500
  UNICOM: "#62ad52", // hunter-green-500
};

const AXIS_TICK_FILL = "#8b7474";
const GRID_STROKE = "#d1c7c7";

interface PayloadItem {
  name?: string;
  value?: number;
  payload?: {
    name?: string;
    value?: number;
    count?: number;
    percentage?: string;
    fill?: string;
  };
  color?: string;
}

function ChartTooltip({
  active,
  payload,
  isPie,
}: {
  active?: boolean;
  payload?: PayloadItem[];
  isPie?: boolean;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0];
  const name = isPie ? item.name : item.payload?.name;
  const value = isPie ? item.value : item.payload?.count;
  const pct = item.payload?.percentage;

  return (
    <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/95 dark:bg-deep-mocha-900/95 px-3 py-2 backdrop-blur-sm text-sm">
      <p
        className="font-semibold text-deep-mocha-800 dark:text-deep-mocha-100"
        style={!isPie ? { fontStyle: "italic" } : undefined}
      >
        {name}
      </p>
      <p className="text-deep-mocha-600 dark:text-deep-mocha-300">
        {(value ?? 0).toLocaleString()} entries
        {pct && ` (${pct})`}
      </p>
    </div>
  );
}

function FamilyPieChart({
  entriesByFamily,
}: {
  entriesByFamily: Record<string, number>;
}) {
  const data = useMemo(() => {
    const total = Object.values(entriesByFamily).reduce((a, b) => a + b, 0);
    return Object.entries(entriesByFamily)
      .map(([key, value], idx) => ({
        name: toSentenceCase(key),
        value,
        percentage: total > 0 ? ((value / total) * 100).toFixed(1) + "%" : "0%",
        fill: FAMILY_COLORS[idx % FAMILY_COLORS.length],
      }))
      .sort((a, b) => b.value - a.value);
  }, [entriesByFamily]);

  const renderLabel = (props: { name?: string | number }) =>
    String(props.name ?? "");

  return (
    <ResponsiveContainer width="100%" height={420}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={140}
          innerRadius={60}
          paddingAngle={2}
          label={renderLabel}
          labelLine={{ stroke: "#8b7474", strokeWidth: 1 }}
          animationDuration={800}
          animationEasing="ease-out"
          stroke="none"
        />
        <Tooltip content={<ChartTooltip isPie />} />
        <Legend
          verticalAlign="bottom"
          iconType="circle"
          iconSize={10}
          wrapperStyle={{ paddingTop: 16 }}
          formatter={(value: string) => (
            <span className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300">
              {value}
            </span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function TopSpeciesBarChart({
  topTenSpecies,
}: {
  topTenSpecies: Record<string, number>;
}) {
  const data = useMemo(() => {
    const total = Object.values(topTenSpecies).reduce((a, b) => a + b, 0);
    return Object.entries(topTenSpecies)
      .map(([key, count]) => ({
        name: toSpeciesName(key),
        slug: key,
        count,
        percentage: total > 0 ? ((count / total) * 100).toFixed(1) + "%" : "0%",
      }))
      .sort((a, b) => b.count - a.count);
  }, [topTenSpecies]);

  return (
    <ResponsiveContainer width="100%" height={Math.max(400, data.length * 44)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 40, bottom: 4, left: 8 }}
        barCategoryGap="20%"
      >
        <defs>
          <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={BAR_GRADIENT_END} />
            <stop offset="100%" stopColor={BAR_GRADIENT_START} />
          </linearGradient>
        </defs>
        <CartesianGrid
          horizontal={false}
          strokeDasharray="3 3"
          stroke="#d1c7c7"
          strokeOpacity={0.4}
        />
        <XAxis
          type="number"
          tickFormatter={(v: number) => v.toLocaleString()}
          tick={{
            fontSize: 12,
            fill: "#8b7474",
          }}
          axisLine={{ stroke: "#d1c7c7", strokeOpacity: 0.5 }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={180}
          tick={<ItalicTick />}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={<ChartTooltip />}
          cursor={{ fill: "rgba(62,173,193,0.08)" }}
        />
        <Bar
          dataKey="count"
          fill="url(#barGradient)"
          radius={[0, 6, 6, 0]}
          animationDuration={800}
          animationEasing="ease-out"
          label={{
            position: "right",
            formatter: (v: unknown) =>
              typeof v === "number" ? v.toLocaleString() : String(v ?? ""),
            fontSize: 12,
            fill: "#8b7474",
          }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ItalicTick(props: {
  x?: number;
  y?: number;
  payload?: { value?: string; offset?: number };
  tickData?: { index?: number };
  visibleTicksCount?: number;
}) {
  const { x = 0, y = 0, payload } = props;
  const displayName = payload?.value ?? "";
  const slug = displayName.toLowerCase().replace(/ /g, "_");

  return (
    <a href={`/species/${slug}`} style={{ cursor: "pointer" }}>
      <text
        x={x}
        y={y}
        dy={4}
        textAnchor="end"
        fontStyle="italic"
        fontSize={13}
        fill="#534646"
        className="dark:fill-deep-mocha-300"
        style={{ textDecoration: "none", textUnderlineOffset: 2 }}
      >
        {displayName}
      </text>
    </a>
  );
}

// ---------------------------------------------------------------------------
// Embedding value distributions (CLIP vs UNICOM)
// ---------------------------------------------------------------------------

interface BoxPlotDatum extends EmbeddingSummary {
  base: number;
  span: number;
  fill: string;
}

function BoxPlotTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload?: BoxPlotDatum }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0]?.payload;
  if (!datum) return null;

  const rows: [string, number][] = [
    ["Maximum", datum.maximum],
    ["Upper whisker", datum.upperWhisker],
    ["Q3", datum.q3],
    ["Median", datum.median],
    ["Q1", datum.q1],
    ["Lower whisker", datum.lowerWhisker],
    ["Minimum", datum.minimum],
  ];

  return (
    <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/95 dark:bg-deep-mocha-900/95 px-3 py-2 backdrop-blur-sm text-sm">
      <p className="font-semibold text-deep-mocha-800 dark:text-deep-mocha-100">
        {datum.embeddingModel}
      </p>
      <p className="mb-1 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
        {datum.dimensions.toLocaleString()} dimensions &middot;{" "}
        {datum.imageCount.toLocaleString()} images &middot;{" "}
        {datum.sampleSize.toLocaleString()} values
      </p>
      {rows.map(([label, value]) => (
        <p
          key={label}
          className="flex justify-between gap-6 text-deep-mocha-600 dark:text-deep-mocha-300"
        >
          <span>{label}</span>
          <span className="tabular-nums">{value.toFixed(3)}</span>
        </p>
      ))}
    </div>
  );
}

/**
 * Draws a single box-and-whisker row.
 *
 * The bar this replaces spans lowerWhisker..upperWhisker, so its `x` and
 * `width` give two known anchors on a linear axis, and the quartiles are
 * interpolated between them.
 */
function BoxWhiskerShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: BoxPlotDatum;
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (!payload) return null;

  const { lowerWhisker, upperWhisker, q1, median, q3, fill } = payload;
  const span = upperWhisker - lowerWhisker;
  if (span <= 0 || width <= 0) return null;

  const toX = (value: number) => x + ((value - lowerWhisker) / span) * width;
  const midY = y + height / 2;
  const capHalf = height * 0.3;

  return (
    <g>
      <line
        x1={toX(lowerWhisker)}
        x2={toX(upperWhisker)}
        y1={midY}
        y2={midY}
        stroke={fill}
        strokeWidth={1.5}
      />
      {[lowerWhisker, upperWhisker].map((value) => (
        <line
          key={value}
          x1={toX(value)}
          x2={toX(value)}
          y1={midY - capHalf}
          y2={midY + capHalf}
          stroke={fill}
          strokeWidth={1.5}
        />
      ))}
      <rect
        x={toX(q1)}
        y={y}
        width={Math.max(toX(q3) - toX(q1), 1)}
        height={height}
        rx={3}
        fill={fill}
        fillOpacity={0.35}
        stroke={fill}
        strokeWidth={1.5}
      />
      <line
        x1={toX(median)}
        x2={toX(median)}
        y1={y}
        y2={y + height}
        stroke={fill}
        strokeWidth={2.5}
      />
    </g>
  );
}

function EmbeddingBoxPlot() {
  const [distributions, setDistributions] = useState<EmbeddingSummary[] | null>(
    null
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadStats = async () => {
      setLoading(true);
      setError(null);
      const data = await fetchEmbeddingStats();
      if (cancelled) return;
      if (data && data.distributions.length > 0) {
        setDistributions(data.distributions);
      } else {
        setError("Embedding distributions are unavailable.");
      }
      setLoading(false);
    };

    loadStats();
    return () => {
      cancelled = true;
    };
  }, []);

  // Component values straddle zero, but stacked bars cannot mix signs, so the
  // whole axis is shifted into positive space and the ticks are shifted back.
  //
  // The axis is scaled to the whiskers rather than the observed extremes: a
  // single far-out value (CLIP reaches ~18x its own IQR) would otherwise
  // squash both boxes to a few percent of the width. The extremes are still
  // reported in the tooltip.
  const { data, offset, domainMax } = useMemo(() => {
    if (!distributions || distributions.length === 0) {
      return { data: [] as BoxPlotDatum[], offset: 0, domainMax: 1 };
    }
    const lowest = Math.min(...distributions.map((d) => d.lowerWhisker));
    const highest = Math.max(...distributions.map((d) => d.upperWhisker));
    const padding = (highest - lowest) * 0.05 || 0.1;
    const shift = padding - lowest;

    return {
      data: distributions.map((d) => ({
        ...d,
        base: d.lowerWhisker + shift,
        span: d.upperWhisker - d.lowerWhisker,
        fill: EMBEDDING_COLORS[d.embeddingModel] ?? AXIS_TICK_FILL,
      })),
      offset: shift,
      domainMax: highest + padding + shift,
    };
  }, [distributions]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <NoData text="Loading embedding distributions..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-burnt-peach-500 p-4 border border-burnt-peach-300 rounded-xl">
        Error: {error}
      </div>
    );
  }

  return (
    <>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
          barCategoryGap="35%"
        >
          <CartesianGrid
            horizontal={false}
            strokeDasharray="3 3"
            stroke={GRID_STROKE}
            strokeOpacity={0.4}
          />
          <XAxis
            type="number"
            domain={[0, domainMax]}
            tickFormatter={(v: number) => (v - offset).toFixed(2)}
            tick={{ fontSize: 12, fill: AXIS_TICK_FILL }}
            axisLine={{ stroke: GRID_STROKE, strokeOpacity: 0.5 }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="embeddingModel"
            width={80}
            tick={{ fontSize: 13, fill: AXIS_TICK_FILL }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<BoxPlotTooltip />}
            cursor={{ fill: "rgba(62,173,193,0.08)" }}
          />
          {/* Transparent spacer positions the visible bar at lowerWhisker. */}
          <Bar
            dataKey="base"
            stackId="box"
            fill="transparent"
            isAnimationActive={false}
          />
          {/* Geometry is derived from this bar's pixel extent, so it must not
              animate: an interpolated width would misplace the quartiles. */}
          <Bar
            dataKey="span"
            stackId="box"
            shape={<BoxWhiskerShape />}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
        Box spans the interquartile range with the median marked; whiskers reach
        1.5&times;IQR. Hover for the full five-number summary, including the
        observed extremes.
      </p>
    </>
  );
}

export default function CollectionCharts({
  entriesByFamily,
  topTenSpecies,
}: {
  entriesByFamily: Record<string, number> | null;
  topTenSpecies: Record<string, number> | null;
}) {
  const cardClasses =
    "rounded-xl p-6 bg-deep-mocha-50/80 dark:bg-deep-mocha-800/80 border border-deep-mocha-200 dark:border-deep-mocha-700 backdrop-blur-sm";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {entriesByFamily && Object.keys(entriesByFamily).length > 0 && (
        <div className={cardClasses}>
          <h3 className="text-xl font-semibold mb-4 text-deep-mocha-900 dark:text-white">
            Entries by Family
          </h3>
          <FamilyPieChart entriesByFamily={entriesByFamily} />
        </div>
      )}

      {topTenSpecies && Object.keys(topTenSpecies).length > 0 && (
        <div className={cardClasses}>
          <h3 className="text-xl font-semibold mb-4 text-deep-mocha-900 dark:text-white">
            Top 10 Species
          </h3>
          <TopSpeciesBarChart topTenSpecies={topTenSpecies} />
        </div>
      )}

      <div className={`${cardClasses} lg:col-span-2`}>
        <h3 className="text-xl font-semibold mb-1 text-deep-mocha-900 dark:text-white">
          Embedding Value Distribution
        </h3>
        <p className="mb-4 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
          Spread of embedding component values for the two models behind image
          search: CLIP (text&rarr;image) and UNICOM (image&rarr;image).
        </p>
        <EmbeddingBoxPlot />
      </div>
    </div>
  );
}
