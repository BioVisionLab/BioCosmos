import React from "react";
import Link from "next/link";

export default function CollectionsPage() {
  const gbifEntries = 123_456; // placeholder
  const lepTraitsEntries = 78_432; // placeholder
  const imageEntries = 50_234; // placeholder
  const gbifSpeciesCount = 9_876; // placeholder

  const stats = [
    { label: "GBIF Entries", value: gbifEntries },
    { label: "LepTraits Entries", value: lepTraitsEntries },
    { label: "Image Entries", value: imageEntries },
    { label: "GBIF Species Count", value: gbifSpeciesCount },
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
      </p>

      <section aria-label="Dataset statistics">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((s) => (
            <article
              key={s.label}
              className="rounded-lg p-6 bg-gradient-to-br from-emerald-200 via-teal-200 to-cyan-200 dark:from-emerald-800 dark:via-teal-800 dark:to-cyan-800 border border-gray-200 dark:border-gray-700 shadow-sm transform transition hover:scale-102"
            >
              <div className="text-4xl font-extrabold text-gray-900 dark:text-white">
                {s.value.toLocaleString()}
              </div>
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                {s.label}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
