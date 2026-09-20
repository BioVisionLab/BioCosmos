import Link from "next/link";

import LandingSectionHeading from "@/components/LandingSection";

export interface CollectionCounts {
  images: number;
  families: number;
  species: number;
}

/**
 * Formatted with an explicit locale: this renders on the server, and an
 * en-US server next to a de-DE browser would otherwise disagree about
 * whether "1,234" means one thousand or one point two.
 */
function formatCount(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-US");
}

/**
 * The size of the collection, in three numbers.
 *
 * Reads the same `/stats/taxon` fields as the collections page
 * (`imageEntries`, `familyCount`, `speciesCount`), so the two cannot
 * disagree. It deliberately does not reuse that page's `CollectionCard`:
 * that is a saturated gradient card built for a dense statistics page,
 * where this sits under two airy rule-and-caption sections and has to
 * belong to them.
 *
 * Every state — pending, available, unavailable — renders the same DOM, so
 * the block is its full height from first paint and the numbers fill in
 * without moving anything below them.
 */
export default function CollectionSummary({
  counts,
  pending = false,
}: {
  counts: CollectionCounts | null;
  pending?: boolean;
}) {
  const cells = [
    { label: "Images", value: counts?.images ?? null },
    { label: "Families", value: counts?.families ?? null },
    { label: "Species", value: counts?.species ?? null },
  ];

  return (
    <section className="w-full mt-16" aria-labelledby="collection-summary-heading">
      <LandingSectionHeading
        id="collection-summary-heading"
        emoji="📊"
        title="Collection Summary"
        description="What the collection holds right now."
      />

      <dl className="mx-auto grid max-w-3xl lg:max-w-4xl grid-cols-3 divide-x divide-deep-mocha-300 dark:divide-deep-mocha-700">
        {cells.map((cell) => (
          // flex-col-reverse: <dt> before <dd> in the DOM, as a description
          // list requires, with the number on top on screen.
          <div
            key={cell.label}
            className="flex flex-col-reverse items-center px-2 sm:px-6"
          >
            <dt className="mt-1 text-xs sm:text-sm uppercase tracking-wider text-deep-mocha-600 dark:text-deep-mocha-400">
              {cell.label}
            </dt>
            <dd className="text-xl sm:text-3xl font-semibold tabular-nums whitespace-nowrap text-hunter-green-600 dark:text-hunter-green-300">
              {formatCount(cell.value)}
            </dd>
          </div>
        ))}
      </dl>

      {/* Two fixed-height lines, always present, so the section is the same
          height whether the counts arrived, are still arriving, or failed. */}
      <p className="mt-3 h-4 text-center text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
        {!pending && !counts ? "Live counts are temporarily unavailable." : " "}
      </p>
      <p className="h-5 text-center text-sm">
        <Link
          href="/collections"
          className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
        >
          See full collection statistics →
        </Link>
      </p>
    </section>
  );
}
