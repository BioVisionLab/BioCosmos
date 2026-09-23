import Link from "next/link";

import LandingSectionHeading, {
  LANDING_CONTAINER,
  LANDING_EYEBROW,
} from "@/components/LandingSection";
import { countryHref, type CountryDiversityRow } from "@/lib/countryDiversity";
import { familyHref } from "@/lib/taxonSlug";

export interface CollectionCounts {
  images: number;
  families: number;
  species: number;
  /** Countries with at least one validated record. */
  countries: number | null;
}

export interface SummaryBar {
  label: string;
  value: number;
  /** Where the row links to, if anywhere. */
  href?: string;
}

/** Rows kept in each breakdown; the rest fold into one "Other" row. */
const FAMILY_ROWS = 6;
const COUNTRY_ROWS = 7;

/**
 * Formatted with an explicit locale: this renders on the server, and an
 * en-US server next to a de-DE browser would otherwise disagree about
 * whether "1,234" means one thousand or one point two.
 */
function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

/**
 * Image counts per validated family, largest first, with the families too
 * small to draw folded into one row that names them.
 */
export function familyBars(
  byFamily: Record<string, number> | null | undefined,
): SummaryBar[] {
  const rows = Object.entries(byFamily ?? {})
    .filter(([, value]) => value > 0)
    .sort(([, a], [, b]) => b - a);
  const shown = rows.slice(0, FAMILY_ROWS);
  const rest = rows.slice(FAMILY_ROWS);
  const bars: SummaryBar[] = shown.map(([label, value]) => ({
    label,
    value,
    href: familyHref(label),
  }));
  if (rest.length > 0) {
    bars.push({
      label: rest.map(([label]) => label).join(", "),
      value: rest.reduce((sum, [, value]) => sum + value, 0),
    });
  }
  return bars;
}

/** The richest countries by distinct species, linked to their species lists. */
export function countryBars(
  countries: CountryDiversityRow[] | null | undefined,
): SummaryBar[] {
  return (countries ?? []).slice(0, COUNTRY_ROWS).map((row) => ({
    label: row.countryName,
    value: row.speciesCount,
    href: countryHref(row.countryCode),
  }));
}

function Bars({
  title,
  unit,
  bars,
  tone,
  rows,
}: {
  title: string;
  unit: string;
  bars: SummaryBar[];
  tone: "green" | "blue";
  /** Reserved row count, so the block is its full height before data. */
  rows: number;
}) {
  const max = bars.reduce((top, bar) => Math.max(top, bar.value), 0);
  const fill =
    tone === "green"
      ? "bg-hunter-green-600 dark:bg-hunter-green-300"
      : "bg-pacific-blue-600 dark:bg-pacific-blue-300";
  return (
    <div className="bc-reveal min-w-0">
      <h3 className="font-display text-lg font-semibold text-deep-mocha-900 dark:text-deep-mocha-50">
        {title}
      </h3>
      <p className={`${LANDING_EYEBROW} mt-1 mb-4`}>{unit}</p>
      <ol className="m-0 grid list-none gap-2.5 p-0">
        {Array.from({ length: rows }, (_, index) => {
          const bar = bars[index];
          if (!bar) {
            return (
              <li key={`empty-${index}`} className="h-5" aria-hidden="true" />
            );
          }
          const label = bar.href ? (
            <Link
              href={bar.href}
              className="truncate hover:text-pacific-blue-700 hover:underline dark:hover:text-pacific-blue-300"
              title={bar.label}
            >
              {bar.label}
            </Link>
          ) : (
            <span className="truncate" title={bar.label}>
              {bar.label}
            </span>
          );
          return (
            <li
              key={bar.label}
              className="grid h-5 grid-cols-[minmax(0,9rem)_minmax(0,1fr)_4.5rem] items-center gap-3 text-sm text-deep-mocha-700 dark:text-deep-mocha-300"
            >
              {label}
              <span className="h-2.5 overflow-hidden rounded-full bg-deep-mocha-200 dark:bg-deep-mocha-700">
                <span
                  className={`bc-bar block h-full rounded-full ${fill}`}
                  style={{ width: `${max > 0 ? Math.max(0.6, (bar.value / max) * 100) : 0}%` }}
                />
              </span>
              <span className="text-right font-label text-xs tabular-nums text-deep-mocha-600 dark:text-deep-mocha-400">
                {formatCount(bar.value)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/**
 * The size of the collection: four figures in the brand gradient, then what
 * they are made of — images by family and species by country.
 *
 * A full-width tinted band, the one place below the hero that breaks out of
 * the page column, so the numbers read as a pause between the browsing
 * sections above and the map below.
 *
 * Reads the same `/stats/taxon` fields as the collections page, and the
 * same `/stats/country` rows as the map, so none of them can disagree.
 *
 * Every state — pending, available, unavailable — renders the same DOM, so
 * the band is its full height from first paint and the numbers fill in
 * without moving anything below them.
 */
export default function CollectionSummary({
  counts,
  families = [],
  countries = [],
  pending = false,
}: {
  counts: CollectionCounts | null;
  families?: SummaryBar[];
  countries?: SummaryBar[];
  pending?: boolean;
}) {
  const cells = [
    { label: "images", value: counts?.images ?? null },
    { label: "species", value: counts?.species ?? null },
    { label: "validated families", value: counts?.families ?? null },
    { label: "countries", value: counts?.countries ?? null },
  ];

  return (
    <section
      className="bc-bleed mt-24 bg-white/60 py-14 sm:py-20 dark:bg-deep-mocha-800/50"
      aria-labelledby="collection-summary-heading"
    >
      <div className="[padding-inline:var(--bc-gutter)]">
        <div className={LANDING_CONTAINER}>
          <LandingSectionHeading
            id="collection-summary-heading"
            eyebrow="Collection summary"
            title="The collection, in numbers"
            contained={false}
            className="bc-reveal"
          />

          <dl className="bc-reveal mt-8 mb-12 grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-4">
            {cells.map((cell) => (
              // flex-col-reverse: <dt> before <dd> in the DOM, as a description
              // list requires, with the number on top on screen.
              <div key={cell.label} className="flex min-w-0 flex-col-reverse gap-1.5">
                <dt className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
                  {cell.label}
                </dt>
                <dd className="bc-gradient-text m-0 truncate font-display text-4xl font-semibold tabular-nums sm:text-5xl">
                  {formatCount(cell.value)}
                </dd>
              </div>
            ))}
          </dl>

          <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
            <Bars
              title="Images by family"
              unit="Validated taxonomy"
              bars={families}
              tone="green"
              rows={FAMILY_ROWS + 1}
            />
            <Bars
              title="Species by country"
              unit="Distinct species, validated coordinates"
              bars={countries}
              tone="blue"
              rows={COUNTRY_ROWS}
            />
          </div>

          {/* Two fixed-height lines, always present, so the band is the same
              height whether the counts arrived, are still arriving, or failed. */}
          <p className="mt-8 h-4 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
            {!pending && !counts ? "Live counts are temporarily unavailable." : " "}
          </p>
          <p className="mt-1 h-5 text-sm">
            <Link
              href="/collections"
              className="text-pacific-blue-600 hover:underline dark:text-pacific-blue-400"
            >
              See full collection statistics →
            </Link>
          </p>
        </div>
      </div>
    </section>
  );
}
