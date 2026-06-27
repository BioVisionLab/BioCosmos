"use client";
import { getSpeciesData, SpeciesData } from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link";
import TabsComponent from "./components/PageTabs";
import SpeciesHeader from "./components/SpeciesTitle";
import { use, useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";

export default function SpeciesPage({
  params,
}: {
  params: Promise<{ speciesName: string }>;
}) {
  const { speciesName } = use(params);

  return (
    <main className="container mx-auto px-2 py-8">
      <SpeciesContent speciesName={speciesName} />
    </main>
  );
}

function SpeciesContent({ speciesName }: { speciesName: string }) {
  const [speciesData, setSpeciesData] = useState<SpeciesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSpeciesData = async () => {
      try {
        const data = await getSpeciesData(speciesName);
        if (data) {
          setSpeciesData(data);
          try {
            // cache species data in localStorage so gallery pages (even new tabs)
            // can reuse it without refetching
            localStorage.setItem(
              `speciesData:${speciesName}`,
              JSON.stringify(data),
            );
          } catch (e) {
            // ignore storage errors
          }
        } else {
          setError("Species data not found.");
        }
      } catch (err) {
        setError("An error occurred while fetching species data.");
      } finally {
        setLoading(false);
      }
    };

    fetchSpeciesData();
  }, [speciesName]);

  if (error) {
    return <p>{error}</p>;
  }

  if (!speciesData && !loading) {
    return <NoData text="No species data available." />;
  }

  return (
    <section>
      {!loading && speciesData && (
        <nav className="text-sm mb-1 text-deep-mocha-600 dark:text-deep-mocha-400 flex items-center gap-2 border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur py-1 px-2 rounded-full">
          <Link
            href={`/family/${speciesData.taxonomy.family}`}
            className="hover:underline"
          >
            {speciesData.taxonomy.family}
          </Link>
          <span>&gt;</span>
          {/* Link to the Genus page */}
          <Link
            href={`/genus/${speciesData.taxonomy.genus}`}
            className="hover:underline italic"
          >
            {speciesData.taxonomy.genus}
          </Link>
          <span>&gt;</span>
          <span className="italic text-deep-mocha-800 dark:text-deep-mocha-200">
            {speciesData.taxonomy.species}
          </span>
        </nav>
      )}
      {loading || !speciesData ? (
        <ImageLoading size={300} msg="Fetching species details" />
      ) : (
        <div>
          <SpeciesHeader
            taxonomy={speciesData.taxonomy}
            name={speciesData.taxonomy.species}
          />

          <div className="mt-8">
            <TabsComponent
              speciesData={speciesData}
              speciesSlug={speciesName}
            />
          </div>
        </div>
      )}
    </section>
  );
}
