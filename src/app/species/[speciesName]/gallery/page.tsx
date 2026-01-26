<<<<<<< HEAD
"use client";

import React, { useEffect, useState } from "react";
import SpecimensTab from "../components/SpecimensTab";
import SpeciesHeader from "../components/SpeciesTitle";
import { getSpeciesData, SpeciesData } from "@/lib/speciesData";
import { ImageLoading } from "@/components/Loadings";

export default function Page({ params }: { params: { speciesName: string } }) {
  const [slug, setSlug] = useState<string>("");
  const [speciesData, setSpeciesData] = useState<SpeciesData | null>(null);
  const [loading, setLoading] = useState(true);

  // `params` may be a Promise in newer Next.js versions. Resolve it
  // inside an effect and store `speciesName` in state instead of
  // accessing `params.speciesName` synchronously.
  useEffect(() => {
    let mounted = true;
    const resolveParams = async () => {
      try {
        const p = await Promise.resolve(params as any);
        if (!mounted) return;
        setSlug(p?.speciesName ?? "");
      } catch (err) {
        if (!mounted) return;
        setSlug("");
      }
    };
    void resolveParams();
    return () => {
      mounted = false;
    };
  }, [params]);

  useEffect(() => {
    let mounted = true;
    if (!slug) {
      // no slug yet; stop loading spinner
      setLoading(false);
      return () => {
        mounted = false;
      };
    }

    const fetchData = async () => {
      setLoading(true);
      try {
        // Try to reuse cached species data saved by the main species page
        let cached: SpeciesData | null = null;
        try {
          const raw = sessionStorage.getItem(`speciesData:${slug}`);
          if (raw) cached = JSON.parse(raw) as SpeciesData;
        } catch (e) {
          /* ignore parse/storage errors */
        }

        if (cached) {
          if (!mounted) return;
          setSpeciesData(cached);
        } else {
          const data = await getSpeciesData(slug);
          if (!mounted) return;
          setSpeciesData(data);
          try {
            if (data) sessionStorage.setItem(`speciesData:${slug}`, JSON.stringify(data));
          } catch (e) {
            /* ignore storage errors */
          }
        }
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
        {speciesData && speciesData.taxonomy ? (
          <SpeciesHeader taxonomy={speciesData.taxonomy} name={speciesData.taxonomy.species} />
        ) : (
          // show a fallback title immediately from the slug while taxonomy loads
          <p className="text-4xl font-semibold">
            <span className="italic">{formatSlugToName(slug)}</span>
          </p>
        )}
      </header>
      <SpecimensTab speciesName={slug} showAll={true} showUmap={false} showImageCount={false} />
    </main>
=======
export default function SpeciesImageGallery({
  speciesName,
}: {
  speciesName: string;
}) {
  // Display simple placeholder for now
  return (
    <div className="w-full aspect-video flex items-center justify-center border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-100 dark:bg-gray-900">
      <p className="text-gray-500 dark:text-gray-400">
        Image Gallery Placeholder
      </p>
    </div>
>>>>>>> api-redesign
  );
}
