import type { Metadata } from "next";

import BackLink from "@/components/BackLink";
import CountryDiversityPanel from "@/components/CountryDiversityPanel";
import { fetchCountryDiversity } from "@/lib/countryDiversity";
import CountryTable from "./CountryTable";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Species Diversity by Country",
};

export default async function CountryDiversityPage() {
  const data = await fetchCountryDiversity();

  return (
    <main className="w-full max-w-5xl mx-auto py-8">
      <BackLink href="/collections" label="Back to Collections" />
      <h1 className="text-3xl font-bold mb-6">Species Diversity by Country</h1>

      <p className="mb-6 text-deep-mocha-700 dark:text-deep-mocha-300">
        Distinct accepted species recorded in each country. A record counts when
        its coordinate falls in exactly one GADM region and nothing contradicts
        that region&apos;s country: either the recorded country was validated,
        or no country was recorded and it is imputed from the coordinate
        (&quot;Imputed images&quot;). Subspecies group with their species;
        records identified only to genus are left out.
      </p>

      {data === null && (
        <div className="mb-6 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          Country statistics are temporarily unavailable.
        </div>
      )}

      <section aria-label="Species diversity map" className="mb-10">
        <CountryDiversityPanel data={data} tableLink={false} />
        {data !== null && data.unresolvedImages > 0 && (
          <p className="mt-1 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
            {data.unresolvedImages.toLocaleString("en-US")} further images fall
            in a GADM region that maps to no ISO country and are not shown.
          </p>
        )}
      </section>

      <CountryTable rows={data?.countries ?? []} />
    </main>
  );
}
