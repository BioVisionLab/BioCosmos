"use client";
import {
  getSpeciesData,
  parseSpeciesSlug,
  SpeciesData,
} from "@/lib/speciesData"; // Import the function and the type
import TabsComponent from "./components/PageTabs";
import TaxonBreadcrumb, { type Crumb } from "@/components/TaxonBreadcrumb";
import { familyHref, genusHref } from "@/lib/taxonSlug";
import SpeciesHeader from "./components/SpeciesTitle";
import { use, useEffect, useMemo, useState } from "react";
import { NoData } from "@/components/NoData";
import { cleanSpeciesName, isSpeciesName } from "@/lib/names";

export default function SpeciesPage({
  params,
}: {
  params: Promise<{ speciesName: string }>;
}) {
  const { speciesName } = use(params);

  return (
    <div className="m-2 ">
      <SpeciesContent speciesName={speciesName} />
    </div>
  );
}

function SpeciesContent({ speciesName }: { speciesName: string }) {
  const [speciesData, setSpeciesData] = useState<SpeciesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // The genus and species are already encoded in the route slug, so the
  // header and breadcrumb can paint immediately instead of waiting on
  // /api/taxon-search (which makes live GBIF and Red List calls).
  const { genus, formattedName } = useMemo(
    () => parseSpeciesSlug(speciesName),
    [speciesName],
  );

  useEffect(() => {
    // Nothing to look up for a slug that does not name a species. No state is
    // touched on the way out: the guard below returns before `loading` is
    // ever consulted, and setting it here would only add a render.
    if (!isSpeciesName(speciesName)) return;

    let mounted = true;

    const fetchSpeciesData = async () => {
      try {
        const data = await getSpeciesData(speciesName);
        if (!mounted) return;
        if (data) {
          setSpeciesData(data);
          try {
            // cache species data in localStorage so gallery pages (even new tabs)
            // can reuse it without refetching
            localStorage.setItem(
              `speciesData:${speciesName}`,
              JSON.stringify(data),
            );
          } catch {
            // ignore storage errors
          }
        } else {
          setError("Species data not found.");
        }
      } catch {
        if (mounted) setError("An error occurred while fetching species data.");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchSpeciesData();

    return () => {
      mounted = false;
    };
  }, [speciesName]);

  // A species page is a page about a species. A slug that names only a genus,
  // or is otherwise not a binomial, has no images to show and no
  // classification to resolve — it used to render a header reading
  // "Unknown sp." over an empty shell. Say so instead; the effect above
  // skips the backend entirely for these.
  if (!isSpeciesName(speciesName)) {
    return (
      <NoData
        text={`"${cleanSpeciesName(speciesName)}" is not a species name. Species pages need a genus and a specific epithet.`}
      />
    );
  }

  if (error) {
    return <p>{error}</p>;
  }

  if (!speciesData && !loading) {
    return <NoData text="No species data available." />;
  }

  const family = speciesData?.taxonomy?.family;

  // The family crumb only appears once taxonomy has resolved; genus and
  // species come straight from the slug, so the trail paints immediately.
  const crumbs: Crumb[] = [{ label: "Home", href: "/" }];
  if (family) crumbs.push({ label: family, href: familyHref(family) });
  crumbs.push({ label: genus, href: genusHref(genus), italic: true });
  crumbs.push({
    label: speciesData?.taxonomy?.species ?? formattedName,
    italic: true,
  });

  return (
    <section>
      <TaxonBreadcrumb items={crumbs} />

      <div>
        <SpeciesHeader
          taxonomy={speciesData?.taxonomy ?? null}
          name={speciesData?.taxonomy?.species ?? formattedName}
        />

        <div className="mt-8">
          <TabsComponent speciesData={speciesData} speciesSlug={speciesName} />
        </div>
      </div>
    </section>
  );
}
