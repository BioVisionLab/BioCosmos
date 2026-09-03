"use client";
import {
  getSpeciesData,
  parseSpeciesSlug,
  SpeciesData,
} from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link";
import TabsComponent from "./components/PageTabs";
import SpeciesHeader from "./components/SpeciesTitle";
import { use, useEffect, useMemo, useState } from "react";
import { NoData } from "@/components/NoData";

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

  if (error) {
    return <p>{error}</p>;
  }

  if (!speciesData && !loading) {
    return <NoData text="No species data available." />;
  }

  const family = speciesData?.taxonomy.family;

  return (
    <section>
      <nav className="text-sm mb-1 text-deep-mocha-600 dark:text-deep-mocha-400 flex items-center gap-2 border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur py-1 px-2 w-fit rounded-full">
        {/* The family link only appears once taxonomy has resolved; genus and
            species come straight from the slug. */}
        {family ? (
          <>
            <Link href={`/family/${family}`} className="hover:underline">
              {family}
            </Link>
            <span>&gt;</span>
          </>
        ) : null}
        <Link href={`/genus/${genus}`} className="hover:underline italic">
          {genus}
        </Link>
        <span>&gt;</span>
        <span className="italic text-deep-mocha-800 dark:text-deep-mocha-200">
          {speciesData?.taxonomy.species ?? formattedName}
        </span>
      </nav>

      <div>
        <SpeciesHeader
          taxonomy={speciesData?.taxonomy ?? null}
          name={speciesData?.taxonomy.species ?? formattedName}
        />

        <div className="mt-8">
          <TabsComponent speciesData={speciesData} speciesSlug={speciesName} />
        </div>
      </div>
    </section>
  );
}
