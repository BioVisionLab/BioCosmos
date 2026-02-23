import React from "react";
import Link from "next/link";

export default function CollectionsPage() {
  const gbifEntries = 123_456; // placeholder
  const lepTraitsEntries = 78_432; // placeholder
  const imageEntries = 50_234; // placeholder
  const gbifSpeciesCount = 9_876; // placeholder

  const stats = [
    { label: "GBIF Occurrences", value: gbifEntries, href: "https://www.gbif.org/" },
    {
      label: "LepTraits Entries",
      value: lepTraitsEntries,
      href: "https://github.com/RiesLabGU/LepTraits",
    },
    { label: "Image Entries", value: imageEntries },
    { label: "GBIF Species Count", value: gbifSpeciesCount },
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
        <Link href="/" className="text-teal-600 hover:underline">
          ← Back to Home
        </Link>
      </div>

      <p className="mb-6 text-gray-700 dark:text-gray-300">
        Statistics on our current dataset, including the number of images, species, and entries in our databases. 
        (CURRENTLY PLACEHOLDER DATA)
      </p>

      <section aria-label="Dataset statistics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((s) => (
            <article
              key={s.label}
              className="rounded-lg p-6 bg-gradient-to-br from-emerald-200 via-teal-200 to-cyan-200 dark:from-emerald-800 dark:via-teal-800 dark:to-cyan-800 border border-gray-200 dark:border-gray-700 shadow-sm transform transition hover:scale-105"
            >
              <div className="text-4xl font-extrabold text-gray-900 dark:text-white">
                {s.value.toLocaleString()}
              </div>
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                {s.href ? (
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-teal-600 dark:decoration-teal-300"
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
              className="rounded-lg p-6 bg-gradient-to-br from-emerald-200 via-teal-200 to-cyan-200 dark:from-emerald-800 dark:via-teal-800 dark:to-cyan-800 border border-gray-200 dark:border-gray-700 shadow-sm transform transition hover:scale-105"
            >
              <div className="text-3xl font-extrabold text-gray-900 dark:text-white">
                {t.value.toLocaleString()}
              </div>
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t.label}</div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
