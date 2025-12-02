"use client";

import React, { useState, useEffect, Suspense } from "react";
import { ImageLoading } from "@/components/Loadings";
import SearchForm from "@/components/SearchForm";
import { Search } from "lucide-react";
import {
  ClassificationSearchResult,
  fetchTaxonClassification,
} from "@/lib/speciesData";
import TextResultCard from "./TextResultCard";

function TextSearchResults({ query }: { query: string }) {
  const [results, setResults] = useState<ClassificationSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // TODO: handle 2 modes, semantic and text search (mode var unused)
  useEffect(() => {
    if (!query) return;

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchTaxonClassification(query);
        if (!data) {
          setResults([]);
          return;
        }
        setResults(data);
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  const handleSearch = (newQuery: string, mode: string) => {
    setError(null);
    setLoading(true);
    setResults([]);
    // Update the URL without refreshing the page
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=text`;
    window.history.pushState({}, "", newUrl);
    // Trigger useEffect to fetch new results
    setTimeout(() => {
      setLoading(false);
      window.location.reload();
    }, 100); // Slight delay to ensure URL is updated
  };

  if (error) {
    return <p className="text-red-500">Error: {error}</p>;
  }

  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <div className="mb-4">
        <a href="/" className="text-blue-600 hover:underline">
          &larr; Back to Home
        </a>
      </div>
      <div id="search-query" className="mb-12 mt-8 text-center">
        <SearchForm
          mode="text"
          icon={Search}
          onSubmit={handleSearch}
          query={query}
          placeholder="Orange butterfly with black lines"
        />
      </div>
      <div id="results-section" className="mt-2">
        <div className="mb-6 text-center">
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        <SearchResults results={results} query={query} loading={loading} />
      </div>
    </div>
  );
}

function SearchResults({
  results,
  query,
  loading,
}: {
  results: ClassificationSearchResult[];
  query: string;
  loading: boolean;
}) {
  if (query.trim() === "" && !loading) {
    return <p>Please enter a search query.</p>;
  }

  if (results.length === 0 && !loading) {
    return <p>No results found for "{query}". Please try a different query.</p>;
  }

  return (
    <>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
          {results.map((item, index) => (
            <Suspense
              key={item.matchCategory + index}
              fallback={<div>Loading species...</div>}
            >
              <TextResultCard classification={item.classification} />
            </Suspense>
          ))}
        </div>
      )}
    </>
  );
}

export default TextSearchResults;
