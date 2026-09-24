import { Suspense } from "react";

import CollectionSummary, {
  familyBars,
  institutionBars,
} from "@/components/CollectionSummary";
import CountryDiversitySection from "@/components/CountryDiversitySection";
import FamilyExplorer from "@/components/FamilyExplorer";
import FeaturedRail from "@/components/FeaturedRail";
import HomePage from "@/components/HomePage";
import SpecimenTray from "@/components/SpecimenTray";
import { fetchCountryDiversity } from "@/lib/countryDiversity";
import { fetchFeaturedSpecies, HERO_SPECIMENS } from "@/lib/featuredSpecies";
import { familiesWithRecords, fetchHigherTaxon } from "@/lib/higherTaxa";
import { fetchTaxonStats } from "@/lib/metaStats";
import { ORDER_NAME } from "@/lib/taxonSlug";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

export default function MainPage() {
  return (
    <HomePage
      specimenTray={
        // Streamed like every data section below, so the sample request
        // cannot hold up the headline and the search box. The fallback is the
        // same tray with its nine compartments empty.
        <Suspense fallback={<SpecimenTray species={null} />}>
          <SpecimenTraySection />
        </Suspense>
      }
      featured={
        <Suspense
          fallback={
            <FeaturedRail species={null} pending labelledBy="featured-heading" />
          }
        >
          <FeaturedRailSection />
        </Suspense>
      }
      familyExplorer={
        <Suspense fallback={<FamilyExplorer families={null} />}>
          <FamilyExplorerSection />
        </Suspense>
      }
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
 * The tray and the rail are two slices of one daily sample. Both call
 * `fetchFeaturedSpecies`, and identical fetches in one render are
 * deduplicated, so this is one request, and no species appears twice.
 */
async function SpecimenTraySection() {
  const featured = await fetchFeaturedSpecies();
  return (
    <SpecimenTray species={featured?.species.slice(0, HERO_SPECIMENS) ?? null} />
  );
}

async function FeaturedRailSection() {
  const featured = await fetchFeaturedSpecies();
  const rest = featured?.species.slice(HERO_SPECIMENS) ?? [];
  return (
    <FeaturedRail
      species={rest.length > 0 ? rest : null}
      labelledBy="featured-heading"
    />
  );
}

/**
 * The same `fetchTaxonStats` the collections page calls. Families is the
 * validated count -- distinct families the taxonomy harmonization resolved
 * with confidence -- rather than the raw recorded count the collections page
 * shows, so the two pages can legitimately disagree on that one number.
 *
 * The country count comes from the same `/stats/country` request the map
 * section below makes, deduplicated in the same way.
 */
async function CollectionSummarySection() {
  const [stats, countries] = await Promise.all([
    fetchTaxonStats(),
    fetchCountryDiversity(),
  ]);
  return (
    <CollectionSummary
      counts={
        stats
          ? {
              images: stats.imageEntries,
              families: stats.familyCountValidated,
              species: stats.speciesCount,
              countries: countries?.countries.length ?? null,
            }
          : null
      }
      families={familyBars(stats?.entriesByFamilyValidated)}
      institutions={institutionBars(
        stats?.institutionCounts,
        stats?.institutionDirectory,
      )}
    />
  );
}

/**
 * The order payload the /order page uses, and the same thirty-day cache
 * entry. A failed request costs this tray its specimens, not the page.
 */
async function FamilyExplorerSection() {
  const order = await fetchHigherTaxon("order", ORDER_NAME).catch(() => null);
  const families = order ? familiesWithRecords(order) : [];
  return <FamilyExplorer families={families.length > 0 ? families : null} />;
}

async function CountryDiversityResolved() {
  return <CountryDiversitySection data={await fetchCountryDiversity()} />;
}
