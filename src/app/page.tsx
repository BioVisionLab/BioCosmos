import { Suspense } from "react";

import CollectionSummary from "@/components/CollectionSummary";
import HomePage from "@/components/HomePage";
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
    />
  );
}

/**
 * The same `fetchTaxonStats` the collections page calls, reading the same
 * three fields, so the two pages cannot report different numbers.
 */
async function CollectionSummarySection() {
  const stats = await fetchTaxonStats();
  return (
    <CollectionSummary
      counts={
        stats
          ? {
              images: stats.imageEntries,
              families: stats.familyCount,
              species: stats.speciesCount,
            }
          : null
      }
    />
  );
}
