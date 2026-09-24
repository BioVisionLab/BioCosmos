import type { HigherTaxon } from "@/lib/higherTaxa";

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

  const stats: { label: string; value: number }[] = [];
  if (taxon.counts.familyCount !== null) {
    stats.push({ label: "families", value: taxon.counts.familyCount });
  }
  if (taxon.counts.genusCount !== null) {
    stats.push({ label: "genera", value: taxon.counts.genusCount });
  }
  stats.push({ label: "species", value: taxon.counts.speciesCount });
  stats.push({ label: "images", value: taxon.counts.imageCount });

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

      <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
        {stats.map((stat) => (
          <div key={stat.label} className="flex items-baseline gap-2">
            {/* The number is the thing; the word beside it is the label, so
                the label is what a screen reader reads first. */}
            <dt className="sr-only">{stat.label}</dt>
            <dd className="text-2xl font-semibold tabular-nums text-hunter-green-700 dark:text-hunter-green-300">
              {stat.value.toLocaleString()}
            </dd>
            <span
              aria-hidden="true"
              className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400"
            >
              {stat.label}
            </span>
          </div>
        ))}
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
      </p>
    </header>
  );
}
