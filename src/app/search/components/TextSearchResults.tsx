"use client";

import React, { useState, useEffect, Suspense } from "react";
import { ImageLoading } from "@/components/Loadings";
import { searchSemantic, MlResultItems } from "@/lib/ml_search";
import SpeciesSearchResultCard from "./ResultCard";

function TextSearchResults({ query }: { query: string }) {
  const [results, setResults] = useState<MlResultItems[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // TODO: handle 2 modes, semantic and text search (mode var unused)
  useEffect(() => {
    if (!query) return;

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await searchSemantic(query);
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
            <ImageLoading size={240} msg="Searching for species" />
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
            <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
              {results.map((item) => (
                <Suspense
                  key={item.imgId}
                  fallback={<div>Loading species...</div>}
                >
                  <SpeciesSearchResultCard species={item} />
                </Suspense>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TextSearchResults;
