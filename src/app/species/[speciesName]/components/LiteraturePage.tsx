"use client";

import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import Info from "@/components/Info";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  CrossRefResult,
  LiteratureResult,
  PublicationsByYear,
  fetchLiterature,
  formatCitation,
} from "@/lib/crossref";
import CopyButton from "@/components/CopyButton";
import Link from "next/link";
import { JSX, useEffect, useRef, useState } from "react";

interface LiteraturePageProps {
  speciesName: string;
}

export function LiteraturePage({ speciesName }: LiteraturePageProps) {
  // Keyed by the species it was fetched for, so a change of species reads as
  // loading without resetting state synchronously inside the effect.
  const [result, setResult] = useState<{
    speciesName: string;
    literature: LiteratureResult | null;
  } | null>(null);

  useEffect(() => {
    // The tab can mount before the species data arrives; wait for a name.
    if (!speciesName.trim()) return;

    let isMounted = true;
    fetchLiterature(speciesName)
      .then((literature) => {
        if (isMounted) setResult({ speciesName, literature });
      })
      .catch((error) => {
        console.error("Error fetching literature data:", error);

        if (isMounted) setResult({ speciesName, literature: null });
      });

    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  const loading = result?.speciesName !== speciesName;
  const literature = loading ? null : result.literature;
  const failed = !loading && literature === null;

  if (loading) {
    return (
      <div className="mx-auto items-center">
        <TextLoading msg="Loading literature data" />
      </div>
    );
  }

  if (failed || !literature) {
    return (
      <div className="mx-auto items-center">
        <NoData text="Literature could not be loaded right now. Please try again later." />
      </div>
    );
  }

  const {
    acceptedName,
    genus,
    synonymsSearched,
    species,
    speciesCount,
    genusRelated,
    genusRelatedCount,
    partial,
    fromYear,
  } = literature;
  const since = fromYear ? ` since ${fromYear}` : "";

  if (speciesCount === 0 && genusRelatedCount === 0) {
    return (
      <div className="mx-auto items-center">
        <NoData text={`No relevant literature found${since}.`} />
        {partial ? <PartialNotice /> : null}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Info>
          <p>
            This list of journal articles, datasets, books, preprints,
            proceedings, reports and dissertations is automatically fetched from{" "}
            <CrossRefLink /> and kept only when the title or abstract matches
            the taxon name. It may still contain irrelevant publications.
          </p>
        </Info>
        {partial ? <PartialNotice /> : null}
      </div>

      <LiteratureSummary literature={literature} />

      {speciesCount > 0 ? (
        <section aria-labelledby="literature-species" className="mb-8">
          <h2 id="literature-species" className="text-xl font-semibold mb-1">
            Publications on <em>{acceptedName}</em>{" "}
            <span className="text-base font-normal text-deep-mocha-500">
              ({speciesCount})
            </span>
          </h2>
          <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 mb-2">
            Publications found for this species{since}.
            {synonymsSearched.length > 0 ? (
              <>
                {" "}
                Searched under the accepted name <em>
                  {acceptedName}
                </em> and{" "}
                {synonymsSearched.length === 1
                  ? "an earlier name"
                  : `${synonymsSearched.length} earlier names`}
                : <NameList names={synonymsSearched} />.
              </>
            ) : null}
          </p>
          <PublicationsList publications={species} section="species" />
        </section>
      ) : null}

      {genusRelated && genus && genusRelatedCount > 0 ? (
        <section aria-labelledby="literature-genus" className="mb-6">
          <h2 id="literature-genus" className="text-xl font-semibold mb-1">
            Related literature on the genus <em>{genus}</em>{" "}
            <span className="text-base font-normal text-deep-mocha-500">
              ({genusRelatedCount})
            </span>
          </h2>
          <PublicationsList publications={genusRelated} section="genus" />
        </section>
      ) : null}

      <CrossRefAttribution isLarge={true} />
    </div>
  );
}

function PartialNotice() {
  return (
    <p className="text-sm text-amber-700 dark:text-amber-400 mt-2">
      CrossRef did not answer every search, so this list may be incomplete. Try
      again in a few minutes.
    </p>
  );
}

/** Italic names joined by commas, e.g. "A, B and C". */
function NameList({ names }: { names: string[] }) {
  return (
    <>
      {names.map((name, i) => (
        <span key={name}>
          {i > 0 ? (i === names.length - 1 ? " and " : ", ") : ""}
          <em>{name}</em>
        </span>
      ))}
    </>
  );
}

function sortYearsDescending(publications: PublicationsByYear) {
  return Object.entries(publications).sort(([yearA], [yearB]) => {
    const a = parseInt(yearA, 10);
    const b = parseInt(yearB, 10);

    if (isNaN(a) && isNaN(b)) return 0;

    if (isNaN(a)) return 1;

    if (isNaN(b)) return -1;

    return b - a;
  });
}

function PublicationsList({
  publications,
  section,
}: {
  publications: PublicationsByYear;
  /** Prefixes each year heading's id, which the summary chart links to. */
  section: "species" | "genus";
}) {
  return (
    <div>
      {sortYearsDescending(publications).map(([year, items]) => (
        <div key={year} className="m-2">
          <h3
            id={`literature-${section}-year-${year}`}
            className="scroll-mt-24 text-xl font-semibold text-pacific-blue-700 dark:text-pacific-blue-400"
          >
            {year}
          </h3>
          <div className="border-l-2 border-pacific-blue-500 mx-2 pl-4 pb-2">
            {items.map((pub, index) => (
              <Publication key={pub.doi ?? `${year}-${index}`} pub={pub} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Publication({ pub }: { pub: CrossRefResult }) {
  return (
    <div>
      <PublicationTypeLabel type={pub.publicationType} />
      <JournalTitle title={pub.title} />
      {pub.matchedVia === "synonym" && pub.matchedName ? (
        <p className="text-xs text-hunter-green-700 dark:text-hunter-green-400 mb-1">
          Published as <em>{pub.matchedName}</em>
        </p>
      ) : null}
      {pub.mentions.length > 0 ? (
        <p className="text-xs text-hunter-green-700 dark:text-hunter-green-400 mb-1">
          Mentions <NameList names={pub.mentions} />
        </p>
      ) : null}
      <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 mb-1">
        {pub.authors.join(", ")}.{" "}
        {pub.published_year ? ` (${pub.published_year}). ` : ""}
        <span className="italic">{pub.journal}</span>
        {pub.volume ? `, ${pub.volume}` : ""}
        {pub.issue ? ` (${pub.issue})` : ""}
        {pub.pages ? `, pp. ${pub.pages}` : ""}.
        {pub.doi ? (
          <span>
            {" "}
            <Link
              href={pub.doi}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
            >
              {pub.doi}
            </Link>
          </span>
        ) : (
          ""
        )}
      </p>
      <div className="flex flex-wrap items-center gap-2 mt-2 mb-4">
        {pub.doi ? <JournalViewButton doi={pub.doi} /> : null}
        <CopyButton
          text={formatCitation(pub)}
          label="Copy citation"
          buttonText="Copy Citation"
          className={secondaryButtonClass}
        />
      </div>
    </div>
  );
}

/*
Each publication type gets a ColorBrewer Dark2 fill, in palette order, with
whichever of black or white text clears WCAG AA (4.5:1) on it; the weakest is
black on #7570b3 at 4.7:1. The fill is the same in both themes, so a label
keeps its contrast in dark mode.

As a chart bar, every fill clears the 3:1 non-text minimum against the
near-black page (the lowest is #666666 at 3.5:1), but #66a61e (3.0:1) and
#e6ab02 (2.1:1) do not against white. In light mode each bar segment is
therefore outlined in its fill darkened to 68%, which clears 4.3:1 or more
against white.
*/
type PublicationTypeKey =
  | "journal-article"
  | "dataset"
  | "book"
  | "preprint"
  | "proceedings"
  | "dissertation"
  | "other";

const publicationTypes: Record<
  PublicationTypeKey,
  { label: string; plural: string; fill: string; stroke: string; text: string }
> = {
  "journal-article": {
    label: "Journal article",
    plural: "Journal articles",
    fill: "bg-[#1b9e77]",
    stroke: "ring-[#126b51]",
    text: "text-black",
  },
  dataset: {
    label: "Dataset",
    plural: "Datasets",
    fill: "bg-[#d95f02]",
    stroke: "ring-[#944101]",
    text: "text-black",
  },
  book: {
    label: "Book or chapter",
    plural: "Books and chapters",
    fill: "bg-[#7570b3]",
    stroke: "ring-[#504c7a]",
    text: "text-black",
  },
  preprint: {
    label: "Preprint",
    plural: "Preprints",
    fill: "bg-[#e7298a]",
    stroke: "ring-[#9d1c5e]",
    text: "text-black",
  },
  proceedings: {
    label: "Proceedings or report",
    plural: "Proceedings and reports",
    fill: "bg-[#66a61e]",
    stroke: "ring-[#457114]",
    text: "text-black",
  },
  dissertation: {
    label: "Dissertation",
    plural: "Dissertations",
    fill: "bg-[#e6ab02]",
    stroke: "ring-[#9c7401]",
    text: "text-black",
  },
  other: {
    label: "Other",
    plural: "Other",
    fill: "bg-[#666666]",
    stroke: "ring-[#454545]",
    text: "text-white",
  },
};

/* Bottom to top in a stacked bar, and the order of the summary tiles. */
const publicationTypeOrder: PublicationTypeKey[] = [
  "journal-article",
  "dataset",
  "book",
  "preprint",
  "proceedings",
  "dissertation",
  "other",
];

/* CrossRef work types, by the category they are shown under. */
const crossrefTypeCategories: Record<string, PublicationTypeKey> = {
  "journal-article": "journal-article",
  dataset: "dataset",
  book: "book",
  "book-chapter": "book",
  "edited-book": "book",
  monograph: "book",
  "posted-content": "preprint",
  "proceedings-article": "proceedings",
  report: "proceedings",
  dissertation: "dissertation",
};

function publicationTypeKey(type?: string): PublicationTypeKey {
  return (type && crossrefTypeCategories[type]) || "other";
}

function PublicationTypeLabel({ type }: { type?: string }) {
  if (!type) return null;

  const { label, fill, text } = publicationTypes[publicationTypeKey(type)];

  return (
    <span
      className={`inline-block rounded px-2 py-0.5 mb-1 text-xs font-semibold ${fill} ${text}`}
    >
      {label}
    </span>
  );
}

type TypeCounts = Record<PublicationTypeKey, number>;

function emptyCounts(): TypeCounts {
  return Object.fromEntries(
    publicationTypeOrder.map((key) => [key, 0]),
  ) as TypeCounts;
}

function countTotal(counts: TypeCounts): number {
  return publicationTypeOrder.reduce((sum, key) => sum + counts[key], 0);
}

/* Spans longer than this are drawn in bins of BIN_YEARS, so columns stay legible. */
const MAX_YEARLY_SPAN = 60;
const BIN_YEARS = 5;

interface YearBin {
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

/* Counts over every publication shown, species and genus sections alike. */
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
clicking it jumps to its newest year in the list, under the species when the
species has papers in that column, else under the genus.
*/
function YearChart({
  summary,
  speciesYears,
}: {
  summary: LiteratureSummaryData & {
    first: number;
    last: number;
    peak: YearBin;
  };
  speciesYears: string[];
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

  const jumpToBin = (bin: YearBin) => {
    const speciesYear = bin.years.find((year) =>
      speciesYears.includes(String(year)),
    );
    const id = speciesYear
      ? `literature-species-year-${speciesYear}`
      : `literature-genus-year-${bin.years[0]}`;
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

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
              onClick={() => jumpToBin(bin)}
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

function LiteratureSummary({ literature }: { literature: LiteratureResult }) {
  const summary = summarizeLiterature([
    literature.species,
    literature.genusRelated,
  ]);
  const { total, byType, first, last, unknownYear, peak } = summary;
  const synonymCount = Object.values(literature.species)
    .flat()
    .filter((pub) => pub.matchedVia === "synonym").length;
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
          speciesYears={Object.keys(literature.species)}
        />
      ) : null}

      <p className="mt-3 text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        {literature.speciesCount} on the species
        {synonymCount > 0 ? ` (${synonymCount} under earlier names)` : ""}
        {literature.genus && literature.genusRelatedCount > 0 ? (
          <>
            {" "}
            · {literature.genusRelatedCount} on the genus{" "}
            <em>{literature.genus}</em>
          </>
        ) : null}
        {unknownYear > 0 ? ` · ${unknownYear} without a year` : ""}
      </p>
    </section>
  );
}

/*
Show title in standard format but detect italic tags for species names
*/
function JournalTitle({ title }: { title: string }) {
  return (
    <p className="font-medium text-lg">
      {(() => {
        const parts: (string | JSX.Element)[] = [];
        // Publishers mark italics with <i>, <em> or JATS <italic>.
        const regex = /<(i|em|italic)>(.*?)<\/\1>/gi;
        let lastIndex = 0;
        let match: RegExpExecArray | null;
        let k = 0;

        while ((match = regex.exec(title)) !== null) {
          if (match.index > lastIndex) {
            parts.push(title.slice(lastIndex, match.index));
          }

          parts.push(<em key={`i-${k++}`}>{match[2]}</em>);
          lastIndex = regex.lastIndex;
        }

        if (lastIndex < title.length) {
          parts.push(title.slice(lastIndex));
        }

        return parts.length ? parts : title;
      })()}
    </p>
  );
}

const publicationButtonBase =
  "inline-flex items-center gap-1 border px-2 py-1 rounded-md text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pacific-blue-700 dark:focus-visible:outline-pacific-blue-300";

/* Primary: white on pacific-blue-700 is 6.3:1, on 800 (hover) 10.5:1. */
const primaryButtonClass = `${publicationButtonBase} border-pacific-blue-700 bg-pacific-blue-700 font-medium text-white hover:border-pacific-blue-800 hover:bg-pacific-blue-800`;

const secondaryButtonClass = `${publicationButtonBase} border-pacific-blue-700 text-pacific-blue-700 hover:bg-pacific-blue-700/10 dark:border-pacific-blue-300 dark:text-pacific-blue-300 dark:hover:bg-pacific-blue-300/10`;

/* `doi` is already a resolvable https://doi.org/... URL. */
function JournalViewButton({ doi }: { doi: string }) {
  return (
    <Link
      href={doi}
      target="_blank"
      rel="noopener noreferrer"
      className={primaryButtonClass}
    >
      View Publication
    </Link>
  );
}
