import type { HigherTaxon } from "@/lib/higherTaxa";

interface Stat {
  label: string;
  value: number;
  /** Catalogue of Life's count at this rank, when there is one to compare. */
  total: number | null;
}

/**
 * A share as a reader wants to see it: a decimal only where it carries
 * information, and never a "0%" for something the collection does hold.
 */
function formatShare(value: number, total: number): string {
  const share = (value / total) * 100;
  if (share > 0 && share < 0.1) return "<0.1%";
  if (share < 10) return `${share.toFixed(1)}%`;
  return `${Math.round(share)}%`;
}

/**
 * The name of an order, family or genus, and how much of the collection sits
 * under it.
 *
 * Deliberately not the species header. `SpeciesTitle` centres a large name
 * because a species page is about one organism; a higher taxon is a
 * container, so this is left-aligned under a rank label and leads with the
 * counts that say how much it holds.
 */
export default function HigherTaxonHeader({ taxon }: { taxon: HigherTaxon }) {
  const italic = taxon.rank === "genus";
  const vernacular = taxon.classification?.vernacularName;
  const authorship = taxon.classification?.authorship;

  const { counts } = taxon;
  const stats: Stat[] = [];
  if (counts.familyCount !== null) {
    stats.push({
      label: "families",
      value: counts.familyCount,
      total: counts.familyTotal,
    });
  }
  if (counts.genusCount !== null) {
    stats.push({
      label: "genera",
      value: counts.genusCount,
      total: counts.genusTotal,
    });
  }
  stats.push({
    label: "species",
    value: counts.speciesCount,
    total: counts.speciesTotal,
  });
  // Images have no Catalogue of Life counterpart to be a share of.
  stats.push({ label: "images", value: counts.imageCount, total: null });
  const hasCoverage = stats.some((stat) => stat.total !== null);

  return (
    <header className="mb-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-hunter-green-700 dark:text-hunter-green-400">
        {taxon.rank}
      </p>
      <h1 className="text-4xl font-bold mt-1 wrap-break-words">
        <span className={italic ? "italic" : ""}>{taxon.name}</span>
        {authorship ? (
          <span className="ml-3 text-xl font-normal text-deep-mocha-500 dark:text-deep-mocha-400">
            {authorship}
          </span>
        ) : null}
      </h1>
      {vernacular ? (
        <p className="text-lg text-deep-mocha-700 dark:text-deep-mocha-300 mt-1">
          {vernacular}
        </p>
      ) : null}

      <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-4">
        {stats.map((stat) => {
          const share =
            stat.total !== null ? formatShare(stat.value, stat.total) : null;
          // Clamped: a genus CoL cannot place still counts here, so a count
          // can in principle edge past the backbone's total.
          const width =
            stat.total !== null
              ? Math.min(100, (stat.value / stat.total) * 100)
              : 0;
          return (
            <div key={stat.label} className="flex flex-col gap-1.5">
              <div className="flex items-baseline gap-2">
                {/* The number is the thing; the word beside it is the label,
                    so the label is what a screen reader reads first. */}
                <dt className="sr-only">{stat.label}</dt>
                <dd className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums text-hunter-green-700 dark:text-hunter-green-300">
                    {stat.value.toLocaleString()}
                  </span>
                  {stat.total !== null ? (
                    <span className="text-sm tabular-nums text-deep-mocha-600 dark:text-deep-mocha-400">
                      <span className="sr-only">out of </span>
                      <span aria-hidden="true">of </span>
                      {stat.total.toLocaleString()}
                    </span>
                  ) : null}
                  <span
                    aria-hidden="true"
                    className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400"
                  >
                    {stat.label}
                  </span>
                  {share ? (
                    <span className="self-center rounded-full px-1.5 text-[0.6875rem] font-medium tabular-nums bg-pacific-blue-500/15 text-pacific-blue-800 dark:text-pacific-blue-200">
                      {share}
                      <span className="sr-only"> covered</span>
                    </span>
                  ) : null}
                </dd>
              </div>
              {stat.total !== null ? (
                // Decorative: the share is already stated in text beside it.
                <div
                  aria-hidden="true"
                  className="h-1 w-full rounded-full bg-deep-mocha-300/40 dark:bg-deep-mocha-600/40 overflow-hidden"
                >
                  <div
                    className="h-full rounded-full bg-linear-to-r from-hunter-green-500 to-pacific-blue-500"
                    // At least a sliver, so a share under one percent still
                    // shows that something is there.
                    style={{ width: `${width > 0 ? Math.max(width, 2) : 0}%` }}
                  />
                </div>
              ) : null}
            </div>
          );
        })}
      </dl>

      {/* Membership here is decided by the harmonized taxonomy: an image
          counts towards a family or genus only once colharmonize has resolved
          its name. The Collections page counts every image as recorded, so
          its totals are the larger of the two. Neither is wrong; they answer
          different questions, and a reader comparing them deserves to know
          which is which. */}
      <p className="mt-2 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
        Counts cover images whose name resolved to an accepted{" "}
        <a
          href="https://www.catalogueoflife.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-600 dark:hover:text-pacific-blue-400"
        >
          Catalogue of Life
        </a>{" "}
        taxon, so they can be lower than the totals on the Collections page.
        {hasCoverage
          ? " Totals and percentages compare them with the accepted families, genera and species Catalogue of Life places in this taxon."
          : null}
      </p>
    </header>
  );
}
