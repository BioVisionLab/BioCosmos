import Link from "next/link";

import { fetchTaxonStats } from "@/lib/metaStats";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export default async function CollectionsPage() {
  const data = await fetchTaxonStats();
  const statsUnavailable = data === null;

  const stats = [
    { label: "Images", value: data?.imageEntries ?? 0 },
    { label: "Families", value: data?.familyCount ?? 0 },
    { label: "Species", value: data?.speciesCount ?? 0 },
    {
      label: "GBIF aggregated",
      value: data?.sourceDbCount?.["gbif"] ?? 0,
      href: "https://www.gbif.org/",
    },
    {
      label: "Ecdysis aggregated",
      value: data?.sourceDbCount?.["ecdysis"] ?? 0,
      href: "https://github.com/RiesLabGU/LepTraits",
    },
    {
      label: "SCANBUGS aggregated",
      value: data?.sourceDbCount?.["scanbugs"] ?? 0,
      href: "https://www.scanbugs.org/",
    },
    { label: "Other aggregated", value: data?.sourceDbCount?.["other"] ?? 0 },
    {
      label: "LepTraits Entries",
      value: data?.lepTraitsEntries ?? 0,
      href: "https://github.com/RiesLabGU/LepTraits",
    },
  ];

  return (
    <main className="max-w-7xl mx-auto p-8">
      <div className="flex items-start justify-between mb-6">
        <h1 className="text-3xl font-bold">Collections</h1>
        <Link href="/" className="text-pacific-blue-600 hover:underline">
          ← Back to Home
        </Link>
      </div>

      <p className="mb-6 text-deep-mocha-700 dark:text-deep-mocha-300">
        Statistics on our current dataset, including the number of images,
        species, LepTrait entries, and entries aggregated by source databases
        (GBIF, Ecdysis, SCANBUGS, and others).
      </p>

      {statsUnavailable && (
        <div className="mb-6 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          Live statistics are temporarily unavailable. The values shown below
          may be outdated.
        </div>
      )}

      <section aria-label="Dataset statistics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((s) => (
            <CollectionCard key={s.label} {...s} />
          ))}
        </div>
      </section>
    </main>
  );
}

function CollectionCard({
  label,
  value,
  href,
}: {
  label: string;
  value: number;
  href?: string;
}) {
  return (
    <article
      key={label}
      className="rounded-lg p-6 bg-gradient-to-br from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 border border-deep-mocha-200 dark:border-deep-mocha-700 shadow-sm transform transition hover:scale-105"
    >
      <div className="text-4xl font-extrabold text-deep-mocha-900 dark:text-white">
        {value.toLocaleString()}
      </div>
      <div className="mt-2 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-pacific-blue-600 dark:decoration-pacific-blue-300"
          >
            {label}
          </a>
        ) : (
          label
        )}
      </div>
    </article>
  );
}
