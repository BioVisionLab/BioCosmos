"use client";

import { useMemo, type ReactNode } from "react";
import Link from "next/link";
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

import {
  countryHref,
  type CountryDiversity,
  type CountryDiversityRow,
} from "@/lib/countryDiversity";
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

const AXIS_TICK_FILL = "#8b7474";
const GRID_STROKE = "#d1c7c7";

/**
 * A chart keeps a floor width and scrolls sideways below it.
 *
 * Recharts sizes its SVG to the container but never clips it, so on a narrow
 * card the pie's outside labels and the bar chart's species names were drawn
 * past the card edge and cut off by the page. Giving each chart a minimum
 * width it is actually legible at — and letting the reader pan to the rest —
 * keeps every label intact at any screen size.
 */
function ChartScroll({
  minWidth,
  children,
}: {
  /** Narrowest width the chart still reads at, in pixels. */
  minWidth: number;
  children: ReactNode;
}) {
  return (
    <div
      className="-mx-2 overflow-x-auto overscroll-x-contain px-2 pb-2"
      // A scroll container is only reachable by keyboard if it can take
      // focus, and it needs a name once it can.
      tabIndex={0}
      role="group"
      aria-label="Chart, scrollable horizontally"
    >
      <div style={{ minWidth }}>{children}</div>
    </div>
  );
}

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

/**
 * Assigns every family one color, stable across both pies.
 *
 * The before and after breakdowns rank families differently once validation
 * folds records into a family the raw data never recorded, so coloring by
 * sorted-value index (as a single pie safely can) would give Nymphalidae one
 * color on one chart and another on the other. Keying off the alphabetical
 * name instead means a slice always means the same family no matter which
 * chart it is read from.
 */
function familyColorMap(
  ...familyRecords: (Record<string, number> | null)[]
): (name: string) => string {
  const names = familyRecords
    .flatMap((record) => (record ? Object.keys(record) : []))
    .map((key) => toSentenceCase(key));
  const uniqueSorted = Array.from(new Set(names)).sort();
  const colorByName = new Map(
    uniqueSorted.map((name, idx) => [name, FAMILY_COLORS[idx % FAMILY_COLORS.length]])
  );
  return (name: string) => colorByName.get(name) ?? AXIS_TICK_FILL;
}

function FamilyPieChart({
  entriesByFamily,
  colorFor,
}: {
  entriesByFamily: Record<string, number>;
  colorFor: (name: string) => string;
}) {
  const data = useMemo(() => {
    const total = Object.values(entriesByFamily).reduce((a, b) => a + b, 0);
    return Object.entries(entriesByFamily)
      .map(([key, value]) => {
        const name = toSentenceCase(key);
        return {
          name,
          value,
          percentage: total > 0 ? ((value / total) * 100).toFixed(1) + "%" : "0%",
          fill: colorFor(name),
        };
      })
      .sort((a, b) => b.value - a.value);
  }, [entriesByFamily, colorFor]);

  // Families under this share sit within a degree or two of each other, so
  // their outside labels landed on top of one another. The legend below and
  // the tooltip still name every slice.
  const LABEL_MIN_SHARE = 0.02;

  const renderLabel = (props: { name?: string | number; percent?: number }) =>
    (props.percent ?? 0) >= LABEL_MIN_SHARE ? String(props.name ?? "") : "";

  const renderLabelLine = (props: {
    points?: { x: number; y: number }[];
    percent?: number;
  }) => {
    const points = props.points ?? [];
    if ((props.percent ?? 0) < LABEL_MIN_SHARE || points.length < 2) {
      return <g />;
    }
    return (
      <polyline
        points={points.map((point) => `${point.x},${point.y}`).join(" ")}
        stroke="#8b7474"
        strokeWidth={1}
        fill="none"
      />
    );
  };

  return (
    // 480px is where the widest family name still fits beside the ring; the
    // radii are proportional so the ring shrinks with the card instead of
    // pushing its own labels off the edge.
    <ChartScroll minWidth={480}>
      <ResponsiveContainer width="100%" height={440}>
      <PieChart margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius="68%"
          innerRadius="32%"
          paddingAngle={2}
          label={renderLabel}
          labelLine={renderLabelLine}
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
    </ChartScroll>
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
    // The name gutter plus a bar long enough to compare: below this the
    // species names were the first thing the card clipped.
    <ChartScroll minWidth={520}>
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
    </ChartScroll>
  );
}

// How many institutions get their own bar; the rest are folded into one
// "+N more" row so a long tail of single-digit contributors cannot push the
// chart's height past what a reader can usefully compare.
const INSTITUTION_BAR_LIMIT = 10;

function InstitutionBarChart({
  institutionCounts,
}: {
  institutionCounts: Record<string, number>;
}) {
  const data = useMemo(() => {
    const total = Object.values(institutionCounts).reduce((a, b) => a + b, 0);
    const sorted = Object.entries(institutionCounts).sort((a, b) => b[1] - a[1]);
    const shown = sorted.slice(0, INSTITUTION_BAR_LIMIT);
    const rest = sorted.slice(INSTITUTION_BAR_LIMIT);
    const restCount = rest.reduce((sum, [, count]) => sum + count, 0);

    const rows = shown.map(([name, count]) => ({ name, count }));
    if (rest.length > 0) {
      rows.push({ name: `+${rest.length} more institutions`, count: restCount });
    }
    return rows.map((row) => ({
      ...row,
      percentage: total > 0 ? ((row.count / total) * 100).toFixed(1) + "%" : "0%",
    }));
  }, [institutionCounts]);

  return (
    <ChartScroll minWidth={480}>
      <ResponsiveContainer width="100%" height={Math.max(360, data.length * 40)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 48, bottom: 4, left: 8 }}
        barCategoryGap="20%"
      >
        <defs>
          <linearGradient id="institutionBarGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={BAR_GRADIENT_END} />
            <stop offset="100%" stopColor={BAR_GRADIENT_START} />
          </linearGradient>
        </defs>
        <CartesianGrid
          horizontal={false}
          strokeDasharray="3 3"
          stroke={GRID_STROKE}
          strokeOpacity={0.4}
        />
        <XAxis
          type="number"
          tickFormatter={(v: number) => v.toLocaleString()}
          tick={{ fontSize: 12, fill: AXIS_TICK_FILL }}
          axisLine={{ stroke: GRID_STROKE, strokeOpacity: 0.5 }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          tick={{ fontSize: 13, fill: "#534646" }}
          className="dark:fill-deep-mocha-300"
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={<ChartTooltip />}
          cursor={{ fill: "rgba(62,173,193,0.08)" }}
        />
        <Bar
          dataKey="count"
          fill="url(#institutionBarGradient)"
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
    </ChartScroll>
  );
}

// How many countries the diversity ranking shows; the full list is a table.
const COUNTRY_BAR_LIMIT = 10;

interface CountryBarDatum {
  name: string;
  code: string;
  species: number;
  images: number;
}

function CountryTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload?: CountryBarDatum }[];
}) {
  const item = active ? payload?.[0]?.payload : undefined;
  if (!item) return null;
  return (
    <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/95 dark:bg-deep-mocha-900/95 px-3 py-2 backdrop-blur-sm text-sm">
      <p className="font-semibold text-deep-mocha-800 dark:text-deep-mocha-100">
        {item.name}
      </p>
      <p className="text-deep-mocha-600 dark:text-deep-mocha-300">
        {item.species.toLocaleString()} species ·{" "}
        {item.images.toLocaleString()} images
      </p>
    </div>
  );
}

/** A country name on the axis, linked to that country's species list. */
function CountryTick(props: {
  x?: number;
  y?: number;
  payload?: { value?: string; index?: number };
  data: CountryBarDatum[];
}) {
  const { x = 0, y = 0, payload, data } = props;
  const row = data.find((d) => d.name === payload?.value);
  const label = (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fontSize={13}
      className="fill-deep-mocha-700 dark:fill-deep-mocha-300"
    >
      {payload?.value}
    </text>
  );
  return row ? (
    <a href={countryHref(row.code)} style={{ cursor: "pointer" }}>
      {label}
    </a>
  ) : (
    label
  );
}

function TopCountriesBarChart({
  countries,
}: {
  countries: CountryDiversityRow[];
}) {
  const data = useMemo<CountryBarDatum[]>(
    () =>
      [...countries]
        .sort(
          (a, b) =>
            b.speciesCount - a.speciesCount ||
            a.countryName.localeCompare(b.countryName),
        )
        .slice(0, COUNTRY_BAR_LIMIT)
        .map((row) => ({
          name: row.countryName,
          code: row.countryCode,
          species: row.speciesCount,
          images: row.imageCount,
        })),
    [countries],
  );

  return (
    <ChartScroll minWidth={480}>
      <ResponsiveContainer width="100%" height={Math.max(360, data.length * 40)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 48, bottom: 4, left: 8 }}
        barCategoryGap="20%"
      >
        <defs>
          <linearGradient id="countryBarGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={BAR_GRADIENT_END} />
            <stop offset="100%" stopColor={BAR_GRADIENT_START} />
          </linearGradient>
        </defs>
        <CartesianGrid
          horizontal={false}
          strokeDasharray="3 3"
          stroke={GRID_STROKE}
          strokeOpacity={0.4}
        />
        <XAxis
          type="number"
          tickFormatter={(v: number) => v.toLocaleString()}
          tick={{ fontSize: 12, fill: AXIS_TICK_FILL }}
          axisLine={{ stroke: GRID_STROKE, strokeOpacity: 0.5 }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          tick={<CountryTick data={data} />}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={<CountryTooltip />}
          cursor={{ fill: "rgba(62,173,193,0.08)" }}
        />
        <Bar
          dataKey="species"
          fill="url(#countryBarGradient)"
          radius={[0, 6, 6, 0]}
          animationDuration={800}
          animationEasing="ease-out"
          label={{
            position: "right",
            formatter: (v: unknown) =>
              typeof v === "number" ? v.toLocaleString() : String(v ?? ""),
            fontSize: 12,
            fill: AXIS_TICK_FILL,
          }}
        />
      </BarChart>
      </ResponsiveContainer>
    </ChartScroll>
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
  entriesByFamilyValidated,
  topTenSpecies,
  institutionCounts,
  countryDiversity,
}: {
  entriesByFamily: Record<string, number> | null;
  entriesByFamilyValidated: Record<string, number> | null;
  topTenSpecies: Record<string, number> | null;
  institutionCounts: Record<string, number> | null;
  countryDiversity: CountryDiversity | null;
}) {
  // min-w-0: a grid item defaults to the width of its content, so without
  // this the charts would widen their own column instead of scrolling.
  const cardClasses =
    "min-w-0 rounded-xl p-4 sm:p-6 bg-deep-mocha-50/80 dark:bg-deep-mocha-800/80 border border-deep-mocha-200 dark:border-deep-mocha-700 backdrop-blur-sm";

  // Both pies read this so the same family is always the same color,
  // whichever side of validation it is shown on.
  const colorFor = familyColorMap(entriesByFamily, entriesByFamilyValidated);

  // Side by side only from xl: at lg the two columns were narrower than the
  // charts' own minimum, so both of them scrolled on a desktop screen with
  // room to spare.
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 lg:gap-8">
      {entriesByFamily && Object.keys(entriesByFamily).length > 0 && (
        <div className={cardClasses}>
          <h3 className="text-xl font-semibold mb-1 text-deep-mocha-900 dark:text-white">
            Family Breakdown — Before Validation
          </h3>
          <p className="mb-4 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
            Every image, grouped by the family recorded at ingestion.
          </p>
          <FamilyPieChart entriesByFamily={entriesByFamily} colorFor={colorFor} />
        </div>
      )}

      {entriesByFamilyValidated && Object.keys(entriesByFamilyValidated).length > 0 && (
        <div className={cardClasses}>
          <h3 className="text-xl font-semibold mb-1 text-deep-mocha-900 dark:text-white">
            Family Breakdown — After Validation
          </h3>
          <p className="mb-4 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
            Images whose family the taxonomy harmonization resolved with
            confidence against the Catalogue of Life backbone.
          </p>
          <FamilyPieChart
            entriesByFamily={entriesByFamilyValidated}
            colorFor={colorFor}
          />
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

      {institutionCounts && Object.keys(institutionCounts).length > 0 && (
        <div className={cardClasses}>
          <h3 className="text-xl font-semibold mb-1 text-deep-mocha-900 dark:text-white">
            Top Institutions
          </h3>
          <p className="mb-4 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
            Proportion of images by holding institution. &quot;Unknown&quot;
            covers images with no institution on record.
          </p>
          <InstitutionBarChart institutionCounts={institutionCounts} />
          <p className="mt-3 text-sm">
            <Link
              href="/collections/providers"
              className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
            >
              See the full institution table →
            </Link>
          </p>
        </div>
      )}

      {countryDiversity && countryDiversity.countries.length > 0 && (
        <div className={`${cardClasses} xl:col-span-2`}>
          <h3 className="text-xl font-semibold mb-1 text-deep-mocha-900 dark:text-white">
            Top 10 Countries by Species Diversity
          </h3>
          <p className="mb-4 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
            Distinct accepted species recorded per country. Countries come from
            the coordinate validation against GADM, not from recorded locality
            text; where no country was recorded it is imputed from the
            coordinate.
          </p>
          <TopCountriesBarChart countries={countryDiversity.countries} />
          <p className="mt-3 text-sm">
            <Link
              href="/collections/country"
              className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
            >
              See all {countryDiversity.countries.length.toLocaleString()} countries →
            </Link>
          </p>
        </div>
      )}
    </div>
  );
}
