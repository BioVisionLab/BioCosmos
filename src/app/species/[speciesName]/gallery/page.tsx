"use client";

import React, { useEffect, useState } from "react";
import SpecimensTab from "../components/SpecimensTab";
import SpeciesHeader from "../components/SpeciesTitle";
import { getSpeciesData, SpeciesData } from "@/lib/speciesData";
import { ImageLoading } from "@/components/Loadings";

export default function Page({ params }: { params: { speciesName: string } }) {
  const slug = params.speciesName ?? "";
  const [speciesData, setSpeciesData] = useState<SpeciesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      try {
        const data = await getSpeciesData(slug);
        if (!mounted) return;
        setSpeciesData(data);
      } catch (err) {
        // ignore, leave speciesData null
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void fetchData();
    return () => {
      mounted = false;
    };
  }, [slug]);

  const formatSlugToName = (s: string) => {
    if (!s) return s;
    const parts = s.replace(/_/g, " ").split(" ").filter(Boolean);
    if (parts.length === 0) return s;
    const genus = parts[0][0]?.toUpperCase() + parts[0].slice(1).toLowerCase();
    const rest = parts.slice(1).map((p) => p.toLowerCase()).join(" ");
    return rest ? `${genus} ${rest}` : genus;
  };

  return (
    <main className="p-6 max-w-7xl mx-auto">
      <header className="mb-6 mt-4 text-center mx-auto">
        {loading ? (
          <div className="flex items-center justify-center">
            <ImageLoading size={64} />
          </div>
        ) : speciesData && speciesData.taxonomy ? (
          <SpeciesHeader taxonomy={speciesData.taxonomy} name={speciesData.taxonomy.species} />
        ) : (
          <p className="text-4xl font-semibold">
            <span className="italic">{formatSlugToName(slug)}</span>
          </p>
        )}
      </header>
      <SpecimensTab speciesName={slug} showAll={true} showUmap={false} />
    </main>
  );
}
