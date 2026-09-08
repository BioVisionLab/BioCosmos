"use client";

import { useEffect, useRef, useState } from "react";
import { MLSearchResultCard } from "@/app/search/components/MlResultCard";
import { ImageLoading } from "@/components/Loadings";
import { ColorSearchResult, searchByColor } from "@/lib/ml_search";

const RESULT_LIMIT = 6;
// The backend removes duplicate species after its vector lookup, so request a
// small candidate pool and then display the best six unique results.
const SEARCH_CANDIDATE_LIMIT = 12;

const SEARCH_OPTIONS = [
  {
    value: "red",
    label: "Red",
    className:
      "border-burnt-peach-400/70 bg-gradient-to-br from-burnt-peach-500 to-burnt-peach-700 text-white shadow-burnt-peach-900/15 hover:from-burnt-peach-400 hover:to-burnt-peach-600 focus-visible:outline-burnt-peach-600 dark:border-burnt-peach-500/60 dark:from-burnt-peach-600 dark:to-burnt-peach-800 dark:hover:from-burnt-peach-500 dark:hover:to-burnt-peach-700",
    labelClassName: "",
    style: undefined,
  },
  {
    value: "blue",
    label: "Blue",
    className:
      "border-pacific-blue-400/70 bg-gradient-to-br from-pacific-blue-500 to-pacific-blue-700 text-white shadow-pacific-blue-900/15 hover:from-pacific-blue-400 hover:to-pacific-blue-600 focus-visible:outline-pacific-blue-600 dark:border-pacific-blue-500/60 dark:from-pacific-blue-600 dark:to-pacific-blue-800 dark:hover:from-pacific-blue-500 dark:hover:to-pacific-blue-700",
    labelClassName: "",
    style: undefined,
  },
  {
    value: "green",
    label: "Green",
    className:
      "border-hunter-green-400/70 bg-gradient-to-br from-hunter-green-500 to-hunter-green-700 text-white shadow-hunter-green-900/15 hover:from-hunter-green-400 hover:to-hunter-green-600 focus-visible:outline-hunter-green-600 dark:border-hunter-green-500/60 dark:from-hunter-green-600 dark:to-hunter-green-800 dark:hover:from-hunter-green-500 dark:hover:to-hunter-green-700",
    labelClassName: "",
    style: undefined,
  },
  {
    value: "owl-like",
    label: "Owl-like",
    className:
      "border-burnt-peach-400/60 text-white shadow-deep-mocha-900/25 hover:brightness-110 focus-visible:outline-deep-mocha-600",
    labelClassName:
      "relative z-10 inline-flex rounded-full border border-white/20 bg-deep-mocha-950/85 px-2 py-0.5 text-white shadow-sm backdrop-blur-sm",
    style: {
      backgroundColor: "#534646",
      backgroundImage:
        "radial-gradient(circle at 18% 50%, #131010 0 6%, #e8987d 7% 13%, #f0baa8 14% 18%, transparent 19%), radial-gradient(circle at 82% 50%, #131010 0 6%, #e8987d 7% 13%, #f0baa8 14% 18%, transparent 19%), linear-gradient(135deg, #8b7474, #382e2e)",
    },
  },
  {
    value: "striped",
    label: "Striped",
    className:
      "border-deep-mocha-500/70 text-white shadow-deep-mocha-900/25 hover:brightness-110 focus-visible:outline-deep-mocha-800",
    labelClassName:
      "relative z-10 inline-flex rounded-full border border-white/20 bg-deep-mocha-950/85 px-2 py-0.5 text-white shadow-sm backdrop-blur-sm",
    style: {
      backgroundColor: "#131010",
      backgroundImage:
        "repeating-linear-gradient(135deg, #131010 0, #131010 10px, #f3f1f1 10px, #f3f1f1 20px)",
    },
  },
] as const;

type SearchOptionValue = (typeof SEARCH_OPTIONS)[number]["value"];

export default function ColorSearch() {
  const [selectedOption, setSelectedOption] =
    useState<SearchOptionValue | null>(null);
  const [results, setResults] = useState<ColorSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const requestNumber = useRef(0);

  useEffect(() => {
    return () => activeRequest.current?.abort();
  }, []);

  const handleOptionSearch = async (option: SearchOptionValue) => {
    activeRequest.current?.abort();

    const controller = new AbortController();
    const currentRequest = ++requestNumber.current;
    activeRequest.current = controller;

    setSelectedOption(option);
    setError(null);
    setLoading(true);

    try {
      const searchResults = await searchByColor(
        option,
        SEARCH_CANDIDATE_LIMIT,
        controller.signal,
      );

      if (currentRequest === requestNumber.current) {
        setResults(searchResults.slice(0, RESULT_LIMIT));
      }
    } catch (searchError) {
      if (controller.signal.aborted) return;

      if (currentRequest === requestNumber.current) {
        setResults([]);
        setError(
          searchError instanceof Error
            ? searchError.message
            : "An unexpected error occurred during visual search.",
        );
      }
    } finally {
      if (currentRequest === requestNumber.current) {
        setLoading(false);
        activeRequest.current = null;
      }
    }
  };

  const selectedLabel = SEARCH_OPTIONS.find(
    (option) => option.value === selectedOption,
  )?.label;

  return (
    <section
      className="w-full max-w-7xl mt-16 px-4 mx-auto"
      aria-labelledby="visual-search-heading"
    >
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 rounded-full bg-gradient-to-r from-burnt-peach-400/50 via-pacific-blue-400/50 to-hunter-green-400/50" />
        <h2
          id="visual-search-heading"
          className="text-xs sm:text-sm font-semibold tracking-wider uppercase text-deep-mocha-700 dark:text-deep-mocha-200"
        >
          Explore Butterflies by Appearance
        </h2>
        <span className="h-px flex-1 rounded-full bg-gradient-to-r from-burnt-peach-400/50 via-pacific-blue-400/50 to-hunter-green-400/50" />
      </div>

      <p className="mt-3 text-center text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
        Try running a quick semantic search. Choose a color or visual trait to
        explore matching butterflies.
      </p>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {SEARCH_OPTIONS.map((option) => {
          const isSelected = selectedOption === option.value;

          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => handleOptionSearch(option.value)}
              style={option.style}
              className={`relative min-w-32 overflow-hidden rounded-full border px-6 py-2.5 text-sm font-semibold shadow-md transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 ${option.className} ${
                isSelected
                  ? "-translate-y-0.5 ring-4 ring-deep-mocha-300/70 shadow-lg dark:ring-deep-mocha-500/70"
                  : "hover:-translate-y-0.5 hover:shadow-lg"
              }`}
            >
              <span className={option.labelClassName}>
                {option.label}
                {loading && isSelected ? "…" : ""}
              </span>
            </button>
          );
        })}
      </div>

      <div
        className={`mt-8 ${selectedOption ? "min-h-48" : ""}`}
        aria-busy={loading}
        aria-live="polite"
      >
        {loading && selectedOption ? (
          <div className="flex justify-center py-8">
            <ImageLoading
              size={160}
              msg={`Finding ${selectedLabel ?? selectedOption} butterflies`}
            />
          </div>
        ) : error ? (
          <p
            role="alert"
            className="mx-auto max-w-2xl rounded-lg border border-burnt-peach-200 bg-burnt-peach-50 px-4 py-3 text-center text-sm text-burnt-peach-700 dark:border-burnt-peach-800 dark:bg-burnt-peach-900/30 dark:text-burnt-peach-300"
          >
            {error}
          </p>
        ) : selectedOption && results.length === 0 ? (
          <p className="text-center text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
            No {selectedLabel ?? selectedOption} butterfly matches were found.
            Try another option.
          </p>
        ) : selectedOption ? (
          <div>
            <p className="mb-5 text-center text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
              Showing {results.length} results for “
              {selectedLabel ?? selectedOption},” ordered from closest to least
              similar.
            </p>
            <div className="grid grid-cols-2 gap-4 mx-auto justify-items-center md:grid-cols-4 lg:grid-cols-6">
              {results.map((result) => (
                <MLSearchResultCard key={result.imgId} data={result} />
              ))}
            </div>
          </div>
        ) : (
          <p className="text-center text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
            Select an option to preview matching butterflies.
          </p>
        )}
      </div>
    </section>
  );
}
