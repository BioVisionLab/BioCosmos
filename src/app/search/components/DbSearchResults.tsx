import { ImageLoading } from "@/components/Loadings";
import SearchForm from "@/components/SearchForm";
import Tips from "@/components/Tips";
import { DbResultItems, searchDatabase } from "@/lib/dbSearch";
import { fetchSpeciesThumbnail } from "@/lib/images";
import { cleanSpeciesName, formatSpeciesNameForUrl } from "@/lib/names";
import { FlaskConical } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Suspense, use, useEffect, useState } from "react";

const IMAGE_SIZE = 128;

function DbSearch({ query }: { query: string }) {
  const [results, setResults] = useState<DbResultItems[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchDatabase(query);
        setResults(response);
      } catch (error) {
        setError("Failed to fetch search results");
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
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}`;
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
        <DbSearchResults results={results} query={query} loading={loading} />
      </div>
    </div>
  );
}

function DbSearchResults({
  results,
  query,
  loading,
}: {
  results: DbResultItems[];
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
    <div>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="mt-5">
          <div>
            <div className="mb-4">
              <h2
                id="other-results"
                className="text-lg text-gray-700 dark:text-gray-200"
              >
                Found {results.length} other results for "{query}"
              </h2>
              <Tips message="Click on an image to view species page" />
            </div>
            <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
              {/* Render remaining results */}
              {results.map((item, index) => (
                <Suspense key={index} fallback={<div>Loading species...</div>}>
                  <DbResultCard data={item} />
                </Suspense>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DbResultCard({ data }: { data: DbResultItems }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchImage = async () => {
      try {
        const url = await fetchSpeciesThumbnail(data.species);
        if (mounted) setImageUrl(url);
      } catch (error) {
        console.error("Error fetching image for DbResultCard:", error);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchImage();
    return () => {
      mounted = false;
    };
  }, [data.species]);

  return (
    <div className="bg-gray-200 dark:bg-gray-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center w-[160px] min-h-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link
          href={`/species/${formatSpeciesNameForUrl(data.species)}`}
          className="flex flex-col items-center justify-between h-full w-full gap-2"
        >
          <div className="flex flex-1 items-center justify-center w-full">
            <Image
              src={imageUrl || `/api/image/${data.species}`}
              alt={`Image of ${data.species}`}
              width={IMAGE_SIZE}
              height={IMAGE_SIZE}
              className="mx-auto object-contain"
            />
          </div>

          <h2 className="text-sm truncate text-center text-gray-400 italic w-full">
            {cleanSpeciesName(data.species)}
          </h2>
          <p className="text-xs text-gray-500 w-full">
            Matched fields:{" "}
            {data.matched_fields
              .map((field) => field.replace(/_/g, " "))
              .join(", ")}
          </p>
        </Link>
      )}
    </div>
  );
}

export { DbSearch };
