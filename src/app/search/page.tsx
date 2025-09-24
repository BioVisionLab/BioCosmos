"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Image from "next/image";
import { fetchThumbnailById } from "@/lib/speciesList";
import { cleanSpeciesName } from "@/lib/names";
import Link from "next/link";
// Define the type for the semantic result object from the Python service
interface SemanticResultItem {
  imgId: string;
  species: string;
  distance: number;
}

// Reusable component for displaying a species card (similar to GenusSpeciesClient)
function SpeciesCard({ species }: { species: SemanticResultItem }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(species.imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchImage();
  }, [species.imgId]);

  const speciesName = cleanSpeciesName(species.species);

  return loading ? (
    <div className="border rounded-md p-4 items-center text-center justify-center">
      <Image
        src="/leaflet/images/butterfly.svg"
        alt="Loading..."
        width={50}
        height={50}
      />
      <p className="text-gray-500">Loading image...</p>
    </div>
  ) : (
    <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl p-4 items-center text-center">
      <Link href={`/species/${species.species}`}>
        <Image
          src={imageUrl || `/api/image/${species.imgId}`}
          alt={`Image of ${species.species}`}
          width={200}
          height={200}
        />

        <h2 className="text-lg truncate text-center text-gray-400 italic">
          {speciesName}
        </h2>
        <p className="text-sm text-gray-500">
          Scores: {species.distance.toPrecision(3)}
        </p>
      </Link>
    </div>
  );
}

function SearchResults({ query, mode }: { query: string; mode: string }) {
  const [results, setResults] = useState<SemanticResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) return;

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/semantic-search?q=${encodeURIComponent(query)}`
        );
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || "Failed to fetch search results");
        }
        const data: SemanticResultItem[] = await response.json();
        // Sort results by distance ascending
        data.sort((a, b) => a.distance - b.distance);
        setResults(data);
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <div className="mb-4">
        <a href="/" className="text-blue-600 hover:underline">
          &larr; Back to Home
        </a>
      </div>
      <div className="mt-2 mb-6 text-center">
        <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
          Search Results
        </h1>
      </div>
      <div className="mt-5">
        {loading ? (
          <div className="flex flex-col items-center mt-24">
            <Image
              src="/leaflet/images/butterfly.svg"
              alt="Loading..."
              width={120}
              height={120}
              className="animate-spin mx-auto"
            />
            <p className="text-gray-500 mt-8">Searching...</p>
          </div>
        ) : error ? (
          <p className="text-red-500">Error: {error}</p>
        ) : results.length === 0 ? (
          <p>No results found for "{query}".</p>
        ) : (
          <div>
            <p className="mb-4">
              Found {results.length} results for "{query}":
            </p>
            <div className="grid grid-flow-row grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
              {results.map((item) => (
                <Suspense
                  key={item.imgId}
                  fallback={<div>Loading species...</div>}
                >
                  <SpeciesCard species={item} />
                </Suspense>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const mode = searchParams.get("mode") || "semantic"; // default to semantic mode
  return <SearchResults query={query} mode={mode} />;
}
