import { ImageLoading } from "@/components/Loadings";
import SearchForm from "@/components/SearchForm";
import Tips from "@/components/Tips";
import {
  DbResultItems,
  SpecimenMetadata,
  searchDatabase,
} from "@/lib/dbSearch";
import { fetchSpeciesThumbnail } from "@/lib/images";
import { cleanSpeciesName, formatSpeciesNameForUrl, speciesUrlFromName } from "@/lib/names";
import { FlaskConical } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const IMAGE_SIZE = 128;

function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function HighlightText({
  text,
  highlight,
  isMatched,
}: {
  text: string | null | undefined;
  highlight: string;
  isMatched: boolean;
}) {
  if (!text) return <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>;
  if (!isMatched || !highlight) return <>{text}</>;

  // Substring matching case-insensitive
  const regex = new RegExp(`(${escapeRegExp(highlight)})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) =>
        regex.test(part) ? (
          <mark
            key={index}
            className="bg-yellow-200 dark:bg-yellow-800/80 text-black dark:text-white px-0.5 rounded-xs"
          >
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

function renderSpeciesLink(
  speciesName: string | null | undefined,
  query: string,
  isMatched: boolean,
) {
  if (!speciesName)
    return <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>;

  const normalized = speciesName.replace(/_/g, " ").trim();
  const parts = normalized.split(/\s+/);

  if (parts.length >= 2) {
    const binomial = `${parts[0]} ${parts[1]}`;
    const rest = parts.slice(2).join(" ");
    const binomialUrl = binomial.toLowerCase().replace(/ /g, "_");

    // Capitalize genus
    const capitalizedBinomial =
      binomial.charAt(0).toUpperCase() + binomial.slice(1);

    return (
      <span className="italic whitespace-nowrap">
        <Link
          href={`/species/${binomialUrl}`}
          className="text-hunter-green-600 dark:text-hunter-green-400 hover:underline font-semibold"
        >
          <HighlightText
            text={capitalizedBinomial}
            highlight={query}
            isMatched={isMatched}
          />
        </Link>
        {rest ? (
          <>
            {" "}
            <HighlightText
              text={rest}
              highlight={query}
              isMatched={isMatched}
            />
          </>
        ) : null}
      </span>
    );
  } else {
    const capitalized =
      speciesName.charAt(0).toUpperCase() + speciesName.slice(1);
    return (
      <span className="italic whitespace-nowrap">
        <HighlightText
          text={capitalized}
          highlight={query}
          isMatched={isMatched}
        />
      </span>
    );
  }
}

function renderCoordinateCell(
  lat: number | null | undefined,
  lon: number | null | undefined,
  matchedFields: string[],
) {
  const hasLat = lat !== null && lat !== undefined;
  const hasLon = lon !== null && lon !== undefined;
  if (!hasLat && !hasLon) {
    return <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>;
  }

  const isMatched =
    matchedFields.includes("lat") ||
    matchedFields.includes("lon") ||
    matchedFields.includes("coordinate");

  const text = `${hasLat ? lat!.toFixed(4) : "—"}, ${hasLon ? lon!.toFixed(4) : "—"}`;

  if (isMatched) {
    return (
      <mark className="bg-yellow-200 dark:bg-yellow-800/80 text-black dark:text-white px-1 rounded-xs">
        {text}
      </mark>
    );
  }

  return <span>{text}</span>;
}

function DbSearch({
  query,
  initialField = "all",
}: {
  query: string;
  initialField?: string;
}) {
  const searchParams = useSearchParams();
  const pageParam = searchParams.get("page") || "1";
  const initialPage = parseInt(pageParam, 10) || 1;

  const [results, setResults] = useState<DbResultItems[]>([]);
  const [specimens, setSpecimens] = useState<SpecimenMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState(initialField);
  const [page, setPage] = useState(initialPage);
  const [totalSpecimens, setTotalSpecimens] = useState(0);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchDatabase(query, field, page);
        setResults(response.results);
        setSpecimens(response.specimens);
        setTotalSpecimens(response.total_specimens);
        setLimit(response.limit);
      } catch (error) {
        setError("Failed to fetch search results");
      } finally {
        setLoading(false);
      }
    };

    if (query) {
      fetchResults();
    }
  }, [query, field, page]);

  const handleSearch = (newQuery: string, mode: string) => {
    setError(null);
    setLoading(true);
    setResults([]);
    setSpecimens([]);
    setPage(1);
    // Update the URL without refreshing the page
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}&field=${encodeURIComponent(field)}&page=1`;
    window.history.pushState({}, "", newUrl);
    // Trigger useEffect to fetch new results
    setTimeout(() => {
      setLoading(false);
      window.location.reload();
    }, 100); // Slight delay to ensure URL is updated
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    const newUrl = `/search?q=${encodeURIComponent(query)}&mode=text&field=${encodeURIComponent(field)}&page=${newPage}`;
    window.history.pushState({}, "", newUrl);
  };

  if (error) {
    return <p className="text-burnt-peach-500">Error: {error}</p>;
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

        <div className="flex items-center gap-3 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
          <label
            htmlFor="search-field-select"
            className="font-semibold tracking-wide uppercase text-xs text-deep-mocha-500 dark:text-deep-mocha-400"
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
                setPage(1);
                const newUrl = `/search?q=${encodeURIComponent(query)}&mode=text&field=${encodeURIComponent(newField)}&page=1`;
                window.history.pushState({}, "", newUrl);
                setTimeout(() => {
                  window.location.reload();
                }, 100);
              }}
              className="appearance-none bg-white/70 dark:bg-deep-mocha-800/60 backdrop-blur border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-hunter-green-500/60 shadow-xs hover:border-hunter-green-500/50 hover:shadow-sm transition-all text-deep-mocha-800 dark:text-deep-mocha-100 cursor-pointer font-medium"
            >
              <option value="all">All Fields</option>
              <optgroup
                label="Taxonomy (Highest to Lowest Rank)"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="kingdom"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Kingdom
                </option>
                <option
                  value="phylum"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Phylum
                </option>
                <option
                  value="class"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Class
                </option>
                <option
                  value="order"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Order
                </option>
                <option
                  value="family"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Family
                </option>
                <option
                  value="species"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Species
                </option>
              </optgroup>
              <optgroup
                label="Specimen Metadata"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="common_name"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Common Name
                </option>
                <option
                  value="class_dv"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Class DV (View)
                </option>
                <option
                  value="sex"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Sex
                </option>
                <option
                  value="life_stage"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Life Stage
                </option>
                <option
                  value="source_db"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Source Database
                </option>
              </optgroup>
              <optgroup
                label="Geography"
                className="bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-500 dark:text-deep-mocha-400 font-semibold text-xs"
              >
                <option
                  value="coordinate"
                  className="text-deep-mocha-800 dark:text-deep-mocha-100 font-normal text-sm"
                >
                  Coordinate (100m radius)
                </option>
              </optgroup>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-deep-mocha-500 dark:text-deep-mocha-400">
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
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-linear-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        <DbSearchResults
          results={results}
          specimens={specimens}
          query={query}
          loading={loading}
          totalSpecimens={totalSpecimens}
          page={page}
          limit={limit}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  );
}

function DbSearchResults({
  results,
  specimens,
  query,
  loading,
  totalSpecimens,
  page,
  limit,
  onPageChange,
}: {
  results: DbResultItems[];
  specimens: SpecimenMetadata[];
  query: string;
  loading: boolean;
  totalSpecimens: number;
  page: number;
  limit: number;
  onPageChange: (newPage: number) => void;
}) {
  if (query.trim() === "" && !loading) {
    return (
      <div className="text-center py-12">
        <p className="text-deep-mocha-500 dark:text-deep-mocha-400 font-medium">
          Please enter a search query.
        </p>
      </div>
    );
  }

  if (results.length === 0 && specimens.length === 0 && !loading) {
    return (
      <div className="text-center py-12">
        <p className="text-deep-mocha-500 dark:text-deep-mocha-400 font-medium">
          No results found for &ldquo;{query}&rdquo;. Please try a different
          query.
        </p>
      </div>
    );
  }

  return (
    <div>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="flex flex-col gap-12 mt-5">
          {/* Top Section: Species Cards Grid */}
          {results.length > 0 && (
            <div>
              <div className="mb-4">
                <h2
                  id="species-results"
                  className="text-2xl font-bold tracking-tight text-deep-mocha-800 dark:text-deep-mocha-100 font-serif"
                >
                  Species pages containing query ({results.length})
                </h2>
                <Tips message="Click on an image card to navigate to the species detail page." />
              </div>
              <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
                {results.map((item, index) => (
                  <Suspense
                    key={index}
                    fallback={<div>Loading species...</div>}
                  >
                    <DbResultCard data={item} />
                  </Suspense>
                ))}
              </div>
            </div>
          )}
          {/* Bottom Section: Specimen Metadata Table */}
          {specimens.length > 0 && (
            <div>
              <div className="mb-4">
                <h2
                  id="specimen-results"
                  className="text-2xl font-bold tracking-tight text-deep-mocha-800 dark:text-deep-mocha-100 font-serif"
                >
                  Specimens matching query ({totalSpecimens})
                </h2>
                <Tips message="Species names are linked to their respective species pages. Text matching the query is highlighted." />
              </div>

              <div className="overflow-x-auto w-full rounded-2xl border border-deep-mocha-200 dark:border-deep-mocha-700/80 shadow-xs bg-white/40 dark:bg-deep-mocha-800/40 backdrop-blur-md">
                <table className="w-full text-left text-sm text-deep-mocha-700 dark:text-deep-mocha-300 border-collapse">
                  <thead className="bg-hunter-green-500/10 dark:bg-hunter-green-500/20 text-hunter-green-800 dark:text-hunter-green-300 font-semibold tracking-wider text-xs uppercase border-b border-deep-mocha-200 dark:border-deep-mocha-700">
                    <tr>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Species
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Kingdom
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Phylum
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Class
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Order
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Family
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Sex
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Life Stage
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Common Name
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        View
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Locality
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Source DB
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-deep-mocha-200/50 dark:divide-deep-mocha-700/50">
                    {specimens.map((specimen, idx) => {
                      const matched = specimen.matched_fields || [];
                      return (
                        <tr
                          key={specimen.img_id || idx}
                          className="hover:bg-hunter-green-50/50 dark:hover:bg-hunter-green-950/20 transition-colors"
                        >
                          <td className="px-4 py-3 align-middle font-medium">
                            {renderSpeciesLink(
                              specimen.species,
                              query,
                              matched.includes("species"),
                            )}
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.kingdom}
                              highlight={query}
                              isMatched={matched.includes("kingdom")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.phylum}
                              highlight={query}
                              isMatched={matched.includes("phylum")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.class}
                              highlight={query}
                              isMatched={matched.includes("class")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.order}
                              highlight={query}
                              isMatched={matched.includes("order")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.family}
                              highlight={query}
                              isMatched={matched.includes("family")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle capitalize">
                            <HighlightText
                              text={specimen.sex}
                              highlight={query}
                              isMatched={matched.includes("sex")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle capitalize">
                            <HighlightText
                              text={specimen.life_stage}
                              highlight={query}
                              isMatched={matched.includes("life_stage")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.common_name}
                              highlight={query}
                              isMatched={matched.includes("common_name")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle uppercase">
                            <HighlightText
                              text={specimen.class_dv}
                              highlight={query}
                              isMatched={matched.includes("class_dv")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            {renderCoordinateCell(
                              specimen.lat,
                              specimen.lon,
                              matched,
                            )}
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.source_db}
                              highlight={query}
                              isMatched={matched.includes("source_db")}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {totalSpecimens > limit && (
                <div className="mt-4 flex items-center justify-between px-4 py-3 bg-white/30 dark:bg-deep-mocha-800/30 backdrop-blur border border-deep-mocha-200 dark:border-deep-mocha-700/80 rounded-2xl">
                  <div className="flex-1 flex justify-between sm:hidden">
                    <button
                      onClick={() => onPageChange(page - 1)}
                      disabled={page <= 1}
                      className="relative inline-flex items-center px-4 py-2 border border-deep-mocha-200 dark:border-deep-mocha-700 text-sm font-medium rounded-xl text-deep-mocha-700 dark:text-deep-mocha-200 bg-white/70 dark:bg-deep-mocha-800/60 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => onPageChange(page + 1)}
                      disabled={page >= Math.ceil(totalSpecimens / limit)}
                      className="ml-3 relative inline-flex items-center px-4 py-2 border border-deep-mocha-200 dark:border-deep-mocha-700 text-sm font-medium rounded-xl text-deep-mocha-700 dark:text-deep-mocha-200 bg-white/70 dark:bg-deep-mocha-800/60 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                    >
                      Next
                    </button>
                  </div>
                  <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
                        Showing{" "}
                        <span className="font-semibold text-hunter-green-600 dark:text-hunter-green-400">
                          {(page - 1) * limit + 1}
                        </span>{" "}
                        to{" "}
                        <span className="font-semibold text-hunter-green-600 dark:text-hunter-green-400">
                          {Math.min(page * limit, totalSpecimens)}
                        </span>{" "}
                        of{" "}
                        <span className="font-semibold text-hunter-green-600 dark:text-hunter-green-400">
                          {totalSpecimens}
                        </span>{" "}
                        specimens
                      </p>
                    </div>
                    <div>
                      <nav
                        className="relative z-0 inline-flex rounded-md shadow-xs -space-x-px"
                        aria-label="Pagination"
                      >
                        <button
                          onClick={() => onPageChange(page - 1)}
                          disabled={page <= 1}
                          className="relative inline-flex items-center px-3 py-2 rounded-l-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/70 dark:bg-deep-mocha-800/60 text-sm font-medium text-deep-mocha-500 dark:text-deep-mocha-400 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                        >
                          <span className="sr-only">Previous</span>
                          <svg
                            className="h-5 w-5"
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                        <span className="relative inline-flex items-center px-4 py-2 border-t border-b border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/40 text-sm font-medium text-deep-mocha-700 dark:text-deep-mocha-300">
                          Page {page} of {Math.ceil(totalSpecimens / limit)}
                        </span>
                        <button
                          onClick={() => onPageChange(page + 1)}
                          disabled={page >= Math.ceil(totalSpecimens / limit)}
                          className="relative inline-flex items-center px-3 py-2 rounded-r-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/70 dark:bg-deep-mocha-800/60 text-sm font-medium text-deep-mocha-500 dark:text-deep-mocha-400 hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                        >
                          <span className="sr-only">Next</span>
                          <svg
                            className="h-5 w-5"
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      </nav>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
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
    <div className="bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center w-[160px] min-h-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <Link
          href={`/species/${speciesUrlFromName(data.species)}`}
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

          <h2 className="text-sm truncate text-center text-deep-mocha-400 italic w-full">
            {cleanSpeciesName(data.species)}
          </h2>
          <p className="text-xs text-deep-mocha-500 w-full">
            Matched:{" "}
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
