import React from "react";
import Link from "next/link";
import { API_HOST } from "@/lib/config";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

interface TaxonStats {
  gbifEntries: number;
  lepTraitsEntries: number;
  imageEntries: number;
  gbifSpeciesCount: number;
}

async function fetchTaxonStats(): Promise<TaxonStats | null> {
  try {
    const response = await fetch(`${API_HOST}/stats/taxon`, {
      next: { revalidate: 3600 },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export default async function CollectionsPage() {
  const data = await fetchTaxonStats();
  const statsUnavailable = data === null;

  const stats = [
    {
      label: "GBIF Occurrences",
      value: data?.gbifEntries ?? 0,
      href: "https://www.gbif.org/",
    },
    {
      label: "LepTraits Entries",
      value: data?.lepTraitsEntries ?? 0,
      href: "https://github.com/RiesLabGU/LepTraits",
    },
    { label: "Image Entries", value: data?.imageEntries ?? 0 },
    { label: "GBIF Species Count", value: data?.gbifSpeciesCount ?? 0 },
  ];

  const orderCount = 120; // placeholder
  const familyCount = 950; // placeholder
  const genusCount = 4_321; // placeholder
  const taxonomicGroupCount = 12; // placeholder

  const taxonomyStats = [
    { label: "Order Count", value: orderCount },
    { label: "Family Count", value: familyCount },
    { label: "Genus Count", value: genusCount },
    { label: "Taxonomic Groups", value: taxonomicGroupCount },
  ];

  return (
    <main className="max-w-5xl mx-auto p-8">
      <div className="flex items-start justify-between mb-6">
        <h1 className="text-3xl font-bold">Collections</h1>
        <Link href="/" className="text-pacific-blue-600 hover:underline">
          ← Back to Home
        </Link>
      </div>

      <p className="mb-6 text-deep-mocha-700 dark:text-deep-mocha-300">
        Statistics on our current dataset, including the number of images,
        species, and entries in our databases.
      </p>

      {statsUnavailable && (
        <div className="mb-6 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          Live statistics are temporarily unavailable. The values shown below may
          be outdated.
        </div>
      )}

      <section aria-label="Dataset statistics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((s) => (
            <article
              key={s.label}
              className="rounded-lg p-6 bg-gradient-to-br from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 border border-deep-mocha-200 dark:border-deep-mocha-700 shadow-sm transform transition hover:scale-105"
            >
              <div className="text-4xl font-extrabold text-deep-mocha-900 dark:text-white">
                {s.value.toLocaleString()}
              </div>
              <div className="mt-2 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
                {s.href ? (
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-pacific-blue-600 dark:decoration-pacific-blue-300"
                  >
                    {s.label}
                  </a>
                ) : (
                  s.label
                )}
              </div>
            </article>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {taxonomyStats.map((t) => (
            <article
              key={t.label}
              className="rounded-lg p-6 bg-gradient-to-br from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 border border-deep-mocha-200 dark:border-deep-mocha-700 shadow-sm transform transition hover:scale-105"
            >
              <div className="text-3xl font-extrabold text-deep-mocha-900 dark:text-white">
                {t.value.toLocaleString()}
              </div>
              <div className="mt-2 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
                {t.label}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
