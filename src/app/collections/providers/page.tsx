
import { fetchTaxonStats } from "@/lib/metaStats";
import ProvidersTable from "./ProvidersTable";
import BackLink from "@/components/BackLink";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export default async function ProvidersPage() {
  const data = await fetchTaxonStats();
  const institutionCounts = data?.institutionCounts ?? null;
  const statsUnavailable = data === null;

  return (
    <main className="w-full max-w-5xl mx-auto py-8">
      <BackLink href="/collections" label="Back to Collections" />
      <h1 className="text-3xl font-bold mb-6">Institutions</h1>

      <p className="mb-6 max-w-3xl text-deep-mocha-700 dark:text-deep-mocha-300">
        Every holding institution behind the collection, with the number of
        images sourced from each. &quot;Unknown&quot; covers images with no
        institution on record — either they were not sourced from GBIF, or
        the record itself carries no institution code.
      </p>

      {statsUnavailable && (
        <div className="mb-6 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          Live statistics are temporarily unavailable.
        </div>
      )}

      <ProvidersTable institutionCounts={institutionCounts} />
    </main>
  );
}
