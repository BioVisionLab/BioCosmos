"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ImageLoading } from "@/components/Loadings";
import { searchSemantic, SemanticSearchResult } from "@/lib/ml_search";
import { MLSearchResultCard } from "./MlResultCard";
import SearchForm from "@/components/SearchForm";
import { FlaskConical } from "lucide-react";
import {
  SemanticSearchDescription,
  SemanticSearchLegend,
} from "@/components/SemanticSearchFunctions";
import Tips from "@/components/Tips";

function SemanticSearchResults({ query }: { query: string }) {
  const [results, setResults] = useState<SemanticSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!query) return;

    // Abort the previous search so a slow, stale response cannot overwrite
    // the results of a newer query.
    const controller = new AbortController();

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await searchSemantic(query, controller.signal);
        if (!controller.signal.aborted) setResults(data);
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        setResults([]);
        setError(
          err instanceof Error && err.message
            ? err.message
            : "An unexpected error occurred",
        );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchResults();
    return () => controller.abort();
  }, [query, attempt]);

  const router = useRouter();

  const handleSearch = (newQuery: string, mode: string) => {
    if (!newQuery.trim()) return;
    setError(null);
    setLoading(true);
    setResults([]);

    if (newQuery === query) {
      setAttempt((previous) => previous + 1);
      return;
    }

    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}`;
    router.push(newUrl);
  };

  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <div className="mb-4">
        <Link href="/" className="text-blue-600 hover:underline">
          &larr; Back to Home
        </Link>
      </div>
      <div id="search-query" className="mb-8 mt-8 text-center space-y-4">
        <SemanticSearchDescription />
        <SearchForm
          mode="semantic"
          icon={FlaskConical}
          onSubmit={handleSearch}
          query={query}
          placeholder="Orange butterfly with black lines"
        />
      </div>
      <div id="results-section" className="mt-2">
        <div className="mb-6 text-center">
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-linear-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        {error ? (
          <p className="text-center text-burnt-peach-500">Error: {error}</p>
        ) : (
          <MlSearchResults results={results} query={query} loading={loading} />
        )}
      </div>
    </div>
  );
}

function MlSearchResults({
  results,
  query,
  loading,
}: {
  results: SemanticSearchResult[];
  query: string;
  loading: boolean;
}) {
  if (query.trim() === "" && !loading) {
    return <p>Please enter a search query.</p>;
  }

  if (results.length === 0 && !loading) {
    return (
      <p>
        No results found for &quot;{query}&quot;. Please try a different query.
      </p>
    );
  }

  return (
    <>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="mt-8">
          <SemanticSearchLegend />
          <div className="mb-4 mt-8">
            <h2 className="text-lg break-words text-deep-mocha-700 dark:text-deep-mocha-200">
              Found {results.length}{" "}
              {results.length === 1 ? "result" : "results"} for &quot;{query}
              &quot;
            </h2>
            <Tips message="Click on an image to view species page" />
          </div>
          <div className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(min(100%,160px),1fr))] gap-4">
            {results.map((item) => (
              <Suspense
                key={item.imgId}
                fallback={<div>Loading species...</div>}
              >
                <MLSearchResultCard data={item} toolNames={item.tool_names} />
              </Suspense>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export default SemanticSearchResults;
