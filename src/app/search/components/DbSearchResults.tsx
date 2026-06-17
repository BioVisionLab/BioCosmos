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

function DbSearch({
  query,
  initialField = "all",
}: {
  query: string;
  initialField?: string;
}) {
  const [results, setResults] = useState<DbResultItems[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState(initialField);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchDatabase(query, field);
        setResults(response);
      } catch (error) {
        setError("Failed to fetch search results");
      } finally {
        setLoading(false);
      }
    };

    if (query) {
      fetchResults();
    }
  }, [query, field]);

  const handleSearch = (newQuery: string, mode: string) => {
    setError(null);
    setLoading(true);
    setResults([]);
    // Update the URL without refreshing the page
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}&field=${encodeURIComponent(field)}`;
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
      <div
        id="search-query"
        className="mb-12 mt-8 text-center flex flex-col items-center gap-4"
      >
        <div className="w-full max-w-2xl">
          <SearchForm
            mode="text"
            icon={FlaskConical}
            onSubmit={handleSearch}
            query={query}
            placeholder="Search database..."
          />
        </div>

        <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
          <label
            htmlFor="search-field-select"
            className="font-semibold tracking-wide uppercase text-xs text-gray-500 dark:text-gray-400"
          >
            Search by:
          </label>
          <div className="relative">
            <select
              id="search-field-select"
              value={field}
              onChange={(e) => {
                const newField = e.target.value;
                setField(newField);
                const newUrl = `/search?q=${encodeURIComponent(query)}&mode=text&field=${encodeURIComponent(newField)}`;
                window.history.pushState({}, "", newUrl);
                setTimeout(() => {
                  window.location.reload();
                }, 100);
              }}
              className="appearance-none bg-white/70 dark:bg-gray-800/60 backdrop-blur border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-emerald-500/60 shadow-xs hover:border-emerald-500/50 hover:shadow-sm transition-all text-gray-800 dark:text-gray-100 cursor-pointer font-medium"
            >
              <option value="all">All Fields</option>
              <optgroup
                label="Taxonomy (Highest to Lowest Rank)"
                className="bg-gray-100 dark:bg-gray-900 text-gray-500 dark:text-gray-400 font-semibold text-xs"
              >
                <option
                  value="kingdom"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Kingdom
                </option>
                <option
                  value="phylum"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Phylum
                </option>
                <option
                  value="class"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Class
                </option>
                <option
                  value="order"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Order
                </option>
                <option
                  value="family"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Family
                </option>
                <option
                  value="species"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Species
                </option>
              </optgroup>
              <optgroup
                label="Specimen Metadata"
                className="bg-gray-100 dark:bg-gray-900 text-gray-500 dark:text-gray-400 font-semibold text-xs"
              >
                <option
                  value="common_name"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Common Name
                </option>
                <option
                  value="class_dv"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Class DV (View)
                </option>
                <option
                  value="sex"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Sex
                </option>
                <option
                  value="life_stage"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Life Stage
                </option>
                <option
                  value="source_db"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Source Database
                </option>
              </optgroup>
              <optgroup
                label="Geography"
                className="bg-gray-100 dark:bg-gray-900 text-gray-500 dark:text-gray-400 font-semibold text-xs"
              >
                <option
                  value="coordinate"
                  className="text-gray-800 dark:text-gray-100 font-normal text-sm"
                >
                  Coordinate (100m radius)
                </option>
              </optgroup>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 dark:text-gray-400">
              <svg
                className="fill-current h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
              >
                <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
              </svg>
            </div>
          </div>
        </div>
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
