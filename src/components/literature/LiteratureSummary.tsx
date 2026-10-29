"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

import {
  type TypeCounts,
  countTotal,
  emptyCounts,
  publicationTypeKey,
  publicationTypeOrder,
  publicationTypes,
} from "@/components/literature/publicationTypes";
import type { PublicationsByYear } from "@/lib/crossref";

/* Spans longer than this are drawn in bins of BIN_YEARS, so columns stay legible. */
const MAX_YEARLY_SPAN = 60;
const BIN_YEARS = 5;

export interface YearBin {
  start: number;
  end: number;
  counts: TypeCounts;
  /** The years in the bin that have publications, newest first. */
  years: number[];
}

interface LiteratureSummaryData {
  total: number;
  byType: TypeCounts;
  first: number | null;
  last: number | null;
  /** 1 for a column per year, BIN_YEARS for a long span. */
  binYears: number;
  /** Every bin from the first year to the last, gaps included, oldest first. */
  bins: YearBin[];
  unknownYear: number;
  peak: YearBin | null;
}

/* Counts over every publication shown, across every list on the page. */
function summarizeLiterature(
  groups: (PublicationsByYear | null)[],
): LiteratureSummaryData {
  const byType = emptyCounts();
  const byYear = new Map<number, TypeCounts>();
  let unknownYear = 0;

  for (const group of groups) {
    if (!group) continue;

    for (const pub of Object.values(group).flat()) {
      const key = publicationTypeKey(pub.publicationType);
      byType[key] += 1;

      if (!pub.published_year) {
        unknownYear += 1;
        continue;
      }

      const counts = byYear.get(pub.published_year) ?? emptyCounts();
      counts[key] += 1;
      byYear.set(pub.published_year, counts);
    }
  }

  const known = [...byYear.keys()];
  const summary: LiteratureSummaryData = {
    total: countTotal(byType),
    byType,
    first: null,
    last: null,
    binYears: 1,
    bins: [],
    unknownYear,
    peak: null,
  };

  if (known.length === 0) return summary;

  const first = Math.min(...known);
  const last = Math.max(...known);
  const binYears = last - first + 1 > MAX_YEARLY_SPAN ? BIN_YEARS : 1;

  for (
    let start = Math.floor(first / binYears) * binYears;
    start <= last;
    start += binYears
  ) {
    const bin: YearBin = {
      start,
      // The last bin stops at the latest year rather than running past it.
      end: Math.min(start + binYears - 1, last),
      counts: emptyCounts(),
      years: [],
    };

    for (let year = bin.end; year >= start; year--) {
      const counts = byYear.get(year);

      if (!counts) continue;

      bin.years.push(year);

      for (const key of publicationTypeOrder) bin.counts[key] += counts[key];
    }

    summary.bins.push(bin);

    if (
      !summary.peak ||
      countTotal(bin.counts) > countTotal(summary.peak.counts)
    ) {
      summary.peak = bin;
    }
  }

  return { ...summary, first, last, binYears };
}

function binLabel(bin: YearBin): string {
  return bin.start === bin.end ? String(bin.start) : `${bin.start}–${bin.end}`;
}

function SummaryTile({
  label,
  value,
  swatch,
}: {
  label: string;
  value: string;
  swatch?: string;
}) {
  return (
    <div className="rounded-lg border border-deep-mocha-600/20 p-3">
      <p className="flex items-center gap-1.5 text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
        {swatch ? (
          <span
            aria-hidden="true"
            className={`inline-block h-2.5 w-2.5 rounded-sm ${swatch}`}
          />
        ) : null}
        {label}
      </p>
      <p className="mt-0.5 text-xl font-semibold">{value}</p>
    </div>
  );
}

function countsDescription(label: string, counts: TypeCounts): string {
  const total = countTotal(counts);
  const parts = publicationTypeOrder
    .filter((key) => counts[key] > 0)
    .map(
      (key) =>
        `${counts[key]} ${(counts[key] === 1 ? publicationTypes[key].label : publicationTypes[key].plural).toLowerCase()}`,
    );

  return `${label}: ${total} ${total === 1 ? "publication" : "publications"}${parts.length ? ` (${parts.join(", ")})` : ""}`;
}

/* Year labels closer together than this are thinned out. */
const MIN_LABEL_SPACING_PX = 40;
/* Label every decade if it fits, else every 20, 50 or 100 years. */
const LABEL_STEPS = [10, 20, 50, 100];
/* The chart width assumed before it has been measured. */
const FALLBACK_CHART_WIDTH = 640;

interface YearTick {
  year: number;
  labeled: boolean;
  isEnd: boolean;
}

/*
A tick at the earliest and latest years and at every decade between them. The
ends are always labeled. Decades are labeled every `step` years, the smallest
step that keeps labels MIN_LABEL_SPACING_PX apart at this width, and a decade
label too close to either end is left off; its tick mark stays.
*/
function yearTicks(first: number, last: number, pxPerYear: number): YearTick[] {
  const step =
    LABEL_STEPS.find((years) => years * pxPerYear >= MIN_LABEL_SPACING_PX) ??
    LABEL_STEPS[LABEL_STEPS.length - 1];
  const minGap = MIN_LABEL_SPACING_PX / pxPerYear;
  const ticks: YearTick[] = [{ year: first, labeled: true, isEnd: true }];

  for (let year = Math.ceil(first / 10) * 10; year < last; year += 10) {
    if (year === first) continue;

    ticks.push({
      year,
      labeled:
        year % step === 0 && year - first >= minGap && last - year >= minGap,
      isEnd: false,
    });
  }

  if (last !== first) ticks.push({ year: last, labeled: true, isEnd: true });

  return ticks;
}

/*
One column per year, or per BIN_YEARS over a long span. Hovering or focusing
a column with publications shows its breakdown by type above the chart;
clicking it hands the column to the caller, which jumps to it in its list.
*/
function YearChart({
  summary,
  onJumpToBin,
}: {
  summary: LiteratureSummaryData & {
    first: number;
    last: number;
    peak: YearBin;
  };
  /** Reveal the column's newest year in a list and scroll to it. */
  onJumpToBin: (bin: YearBin) => void;
}) {
  const { bins, binYears, first, last, peak } = summary;
  const [activeStart, setActiveStart] = useState<number | null>(null);
  const active = bins.find(({ start }) => start === activeStart);
  const unit = binYears === 1 ? "year" : `${binYears} years`;
  const chartRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(FALLBACK_CHART_WIDTH);

  useEffect(() => {
    const chart = chartRef.current;

    if (!chart) return;

    const observer = new ResizeObserver(([entry]) =>
      setChartWidth(entry.contentRect.width),
    );
    observer.observe(chart);

    return () => observer.disconnect();
  }, []);

  const pxPerYear = chartWidth / (bins.length * binYears);

  const tickLeft = (year: number) => {
    const column = Math.floor((year - bins[0].start) / binYears);

    return `${((column + 0.5) / bins.length) * 100}%`;
  };

  return (
    <div className="mt-4">
      <p
        aria-live="polite"
        className="mb-1.5 min-h-4 text-xs text-deep-mocha-600 dark:text-deep-mocha-400"
      >
        {active
          ? countsDescription(binLabel(active), active.counts)
          : `Publications per ${unit} (peak ${countTotal(peak.counts)} in ${binLabel(peak)}). Select a bar to jump to it.`}
      </p>
      <div
        ref={chartRef}
        role="group"
        aria-label={`Publications per ${unit} from ${first} to ${last}`}
        className="flex h-20 items-end gap-0.5 border-b border-deep-mocha-600/50"
        onMouseLeave={() => setActiveStart(null)}
      >
        {bins.map((bin) => {
          const binTotal = countTotal(bin.counts);
          const segments = publicationTypeOrder.map((key) =>
            bin.counts[key] > 0 ? (
              <div
                key={key}
                className={`w-full rounded-[1px] ring-1 ring-inset dark:ring-0 ${publicationTypes[key].fill} ${publicationTypes[key].stroke}`}
                style={{
                  height: `${(bin.counts[key] / countTotal(peak.counts)) * 100}%`,
                }}
              />
            ) : null,
          );

          if (binTotal === 0) {
            return <div key={bin.start} className="h-full min-w-0 flex-1" />;
          }

          return (
            <button
              key={bin.start}
              type="button"
              aria-label={`${countsDescription(binLabel(bin), bin.counts)}. Jump to ${bin.years[0]}.`}
              className={`flex h-full min-w-0 flex-1 cursor-pointer flex-col-reverse gap-px rounded-t-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-pacific-blue-700 dark:focus-visible:outline-pacific-blue-300 ${activeStart === bin.start ? "bg-deep-mocha-500/20" : ""}`}
              onMouseEnter={() => setActiveStart(bin.start)}
              onFocus={() => setActiveStart(bin.start)}
              onBlur={() => setActiveStart(null)}
              onClick={() => onJumpToBin(bin)}
            >
              {segments}
            </button>
          );
        })}
      </div>
      <div
        aria-hidden="true"
        className="relative mt-0.5 h-5 text-xs text-deep-mocha-500"
      >
        {yearTicks(first, last, pxPerYear).map(({ year, labeled, isEnd }) => (
          <span
            key={year}
            className={`absolute top-0 flex -translate-x-1/2 flex-col items-center ${isEnd ? "font-medium text-deep-mocha-700 dark:text-deep-mocha-300" : ""}`}
            style={{ left: tickLeft(year) }}
          >
            <span className="h-1 w-px bg-deep-mocha-600/50" />
            {labeled ? year : null}
          </span>
        ))}
      </div>
    </div>
  );
}

/*
Tiles for the total, each publication type and the year range, over every
list given, then the per-year chart and a line the caller writes. The count
of works without a year is appended to that line.
*/
export function LiteratureSummary({
  lists,
  footer,
  onJumpToBin,
}: {
  lists: (PublicationsByYear | null)[];
  footer: ReactNode;
  onJumpToBin: (bin: YearBin) => void;
}) {
  const summary = summarizeLiterature(lists);
  const { total, byType, first, last, unknownYear, peak } = summary;
  let yearRange = "Unknown";

  if (first && last) {
    yearRange = first === last ? String(first) : `${first}–${last}`;
  }

  // Journal articles always, for scale; every other type only when present.
  const shownTypes = publicationTypeOrder.filter(
    (key) => key === "journal-article" || byType[key] > 0,
  );

  return (
    <section
      aria-labelledby="literature-summary"
      className="mb-8 rounded-lg border border-deep-mocha-600/30 p-4"
    >
      <h2 id="literature-summary" className="sr-only">
        Summary of publications
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryTile label="Total" value={String(total)} />
        {shownTypes.map((key) => (
          <SummaryTile
            key={key}
            label={publicationTypes[key].plural}
            value={String(byType[key])}
            swatch={publicationTypes[key].fill}
          />
        ))}
        <SummaryTile label="Years" value={yearRange} />
      </div>

      {peak && first !== null && last !== null ? (
        <YearChart
          summary={{ ...summary, first, last, peak }}
          onJumpToBin={onJumpToBin}
        />
      ) : null}

      <p className="mt-3 text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        {footer}
        {unknownYear > 0 ? ` · ${unknownYear} without a year` : ""}
      </p>
    </section>
  );
}
