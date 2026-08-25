"use client";

import { useMemo } from "react";
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
    </div>
  );
}
