"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter } from "next/navigation";
import { ImageLoading } from "@/components/Loadings";
import { searchSemantic, MlResultItems } from "@/lib/ml_search";
import { MLSearchResultCard, TopResultCard } from "./MlResultCard";
import SearchForm from "@/components/SearchForm";
import { FlaskConical } from "lucide-react";
import Tips from "@/components/Tips";

function SemanticSearchResults({ query }: { query: string }) {
  const [results, setResults] = useState<MlResultItems[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) return;

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await searchSemantic(query);
        setResults(data);
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  const router = useRouter();

  const handleSearch = (newQuery: string, mode: string) => {
    if (!newQuery.trim()) return;
    setError(null);
    setLoading(true);
    setResults([]);

    // Utilize Next.js app router for seamless single-page client transitions
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}`;
    router.push(newUrl);
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
          mode="semantic"
          icon={FlaskConical}
          onSubmit={handleSearch}
          query={query}
          placeholder="Orange butterfly with black lines"
        />
      </div>
      <div id="results-section" className="mt-2">
        <div className="mb-6 text-center">
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-linear-to-r from-emerald-500 via-teal-500 to-cyan-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        <MlSearchResults results={results} query={query} loading={loading} />
      </div>
    </div>
  );
}

function MlSearchResults({
  results,
  query,
  loading,
}: {
  results: MlResultItems[];
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
        <div className="mt-8">
          <div id="top-results" className="mb-6">
            <Suspense fallback={<div>Loading top species...</div>}>
              <TopResultCard data={results[0]} />
            </Suspense>
          </div>
          <div>
            {results.length > 1 && (
              <>
                <div className="mb-4">
                  <h2
                    id="other-results"
                    className="text-lg text-gray-700 dark:text-gray-200"
                  >
                    Found {results.length - 1} other results for "{query}"
                  </h2>
                  <Tips message="Click on an image to view species page" />
                </div>
                <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
                  {/* Render remaining results */}
                  {results.slice(1).map((item) => (
                    <Suspense
                      key={item.imgId}
                      fallback={<div>Loading species...</div>}
                    >
                      <MLSearchResultCard data={item} />
                    </Suspense>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default SemanticSearchResults;
