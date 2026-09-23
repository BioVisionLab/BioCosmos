import { Suspense } from "react";

import CollectionSummary from "@/components/CollectionSummary";
import CountryDiversitySection from "@/components/CountryDiversitySection";
import HomePage from "@/components/HomePage";
import { fetchCountryDiversity } from "@/lib/countryDiversity";
import { fetchTaxonStats } from "@/lib/metaStats";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export default function MainPage() {
  return (
    <HomePage
      dataSummary={
        // Streamed, so the stats request — which has no timeout — cannot
        // hold up the hero and the search box. The fallback is the same
        // component in its pending state, so the reserved height is
        // identical by construction rather than by a matching guess.
        <Suspense fallback={<CollectionSummary counts={null} pending />}>
          <CollectionSummarySection />
        </Suspense>
      }
      countryDiversity={
        // Its own boundary, so the summary numbers never wait on the map data.
        <Suspense fallback={<CountryDiversitySection data={null} pending />}>
          <CountryDiversityResolved />
        </Suspense>
      }
    />
  );
}

/**
 * The same `fetchTaxonStats` the collections page calls. Families is the
 * validated count -- distinct families the taxonomy harmonization resolved
 * with confidence -- rather than the raw recorded count the collections page
 * shows, so the two pages can legitimately disagree on that one number.
 */
async function CollectionSummarySection() {
  const stats = await fetchTaxonStats();
  return (
    <CollectionSummary
      counts={
        stats
          ? {
              images: stats.imageEntries,
              families: stats.familyCountValidated,
              species: stats.speciesCount,
            }
          : null
      }
    />
  );
}

async function CountryDiversityResolved() {
  return <CountryDiversitySection data={await fetchCountryDiversity()} />;
}
