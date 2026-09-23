
import { fetchCountryDiversity } from "@/lib/countryDiversity";
import { fetchTaxonStats } from "@/lib/metaStats";
import CollectionCharts from "./CollectionCharts";
import BackLink from "@/components/BackLink";
import { SOURCE_DB_HOMEPAGES } from "@/lib/imageMetadata";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export default async function CollectionsPage() {
  const [data, countryDiversity] = await Promise.all([
    fetchTaxonStats(),
    fetchCountryDiversity(),
  ]);
  const statsUnavailable = data === null;

  const summaryStats = [
    { label: "Images", value: data?.imageEntries ?? 0 },
    { label: "Families", value: data?.familyCount ?? 0 },
    { label: "Species", value: data?.speciesCount ?? 0 },
    {
      label: "LepTraits Entries",
      value: data?.lepTraitsEntries ?? 0,
      href: "https://github.com/RiesLabGU/LepTraits",
    },
  ];

  const sourceStats = [
    {
      label: "GBIF",
      value: data?.sourceDbCount?.["gbif"] ?? 0,
      href: SOURCE_DB_HOMEPAGES.gbif,
    },
    {
      label: "Ecdysis",
      value: data?.sourceDbCount?.["ecdysis"] ?? 0,
      href: SOURCE_DB_HOMEPAGES.ecdysis,
    },
    {
      label: "SCANBUGS",
      value: data?.sourceDbCount?.["scanbugs"] ?? 0,
      href: SOURCE_DB_HOMEPAGES.scanbugs,
    },
    {
      label: "Multiple Sources",
      value: data?.sourceDbCount?.["multiple"] ?? 0,
    },
  ];

  return (
    <main className="w-full max-w-7xl 2xl:max-w-[88rem] mx-auto py-8">
      <BackLink />
      <h1 className="text-3xl font-bold mb-6">Collections</h1>

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
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {summaryStats.map((s) => (
            <CollectionCard key={s.label} {...s} />
          ))}
        </div>
      </section>

      <section
        aria-label="Aggregated entries by source databases"
        className="mt-12"
      >
        <h2 className="text-2xl font-semibold mb-4 ">Metadata Sources</h2>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 mb-4">
          Image and metadata are provided by museum institutions and
          aggregated by data aggregators (GBIF, Ecdysis, and SCANBUGS). A
          record published to more than one aggregator is counted under
          &quot;Multiple Sources&quot; rather than a single one.
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {sourceStats.map((s) => (
            <CollectionCard key={s.label} {...s} />
          ))}
        </div>
      </section>

      <section aria-label="Collection visualizations" className="mt-12">
        <h2 className="text-2xl font-semibold mb-4">Dataset Breakdown</h2>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 mb-6">
          Proportion of image entries across butterfly families before and
          after taxonomy validation, the top ten most-represented species in
          the collection, the holding institutions behind the collection, and
          the ten countries with the most species recorded.
        </p>
        <CollectionCharts
          entriesByFamily={data?.entriesByFamily ?? null}
          entriesByFamilyValidated={data?.entriesByFamilyValidated ?? null}
          topTenSpecies={data?.topTenSpecies ?? null}
          institutionCounts={data?.institutionCounts ?? null}
          countryDiversity={countryDiversity}
        />
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
      className="rounded-lg p-4 sm:p-6 bg-gradient-to-br from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 border border-deep-mocha-200 dark:border-deep-mocha-700 transform transition hover:scale-105"
    >
      <div className="text-3xl sm:text-4xl font-extrabold tabular-nums text-deep-mocha-900 dark:text-white">
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
