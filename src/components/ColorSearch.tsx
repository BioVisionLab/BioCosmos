"use client";

import { useEffect, useRef, useState } from "react";
import { MLSearchResultCard } from "@/app/search/components/MlResultCard";
import { ImageLoading } from "@/components/Loadings";
import { ColorSearchResult, searchByColor } from "@/lib/ml_search";

const RESULT_LIMIT = 15;

const COLOR_OPTIONS = [
  {
    value: "red",
    label: "Red",
    className:
      "bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600 dark:bg-red-700 dark:hover:bg-red-600",
  },
  {
    value: "blue",
    label: "Blue",
    className:
      "bg-blue-600 text-white hover:bg-blue-500 focus-visible:outline-blue-600 dark:bg-blue-700 dark:hover:bg-blue-600",
  },
  {
    value: "green",
    label: "Green",
    className:
      "bg-green-600 text-white hover:bg-green-500 focus-visible:outline-green-600 dark:bg-green-700 dark:hover:bg-green-600",
  },
] as const;

type ColorName = (typeof COLOR_OPTIONS)[number]["value"];

export default function ColorSearch() {
  const [selectedColor, setSelectedColor] = useState<ColorName | null>(null);
  const [results, setResults] = useState<ColorSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const requestNumber = useRef(0);

  useEffect(() => {
    return () => activeRequest.current?.abort();
  }, []);

  const handleColorSearch = async (color: ColorName) => {
    activeRequest.current?.abort();

    const controller = new AbortController();
    const currentRequest = ++requestNumber.current;
    activeRequest.current = controller;

    setSelectedColor(color);
    setError(null);
    setLoading(true);

    try {
      const searchResults = await searchByColor(
        color,
        RESULT_LIMIT,
        controller.signal,
      );

      if (currentRequest === requestNumber.current) {
        setResults(searchResults);
      }
    } catch (searchError) {
      if (controller.signal.aborted) return;

      if (currentRequest === requestNumber.current) {
        setResults([]);
        setError(
          searchError instanceof Error
            ? searchError.message
            : "An unexpected error occurred during color search.",
        );
      }
    } finally {
      if (currentRequest === requestNumber.current) {
        setLoading(false);
        activeRequest.current = null;
      }
    }
  };

  return (
    <section
      className="w-full max-w-7xl mt-16 px-4 mx-auto"
      aria-labelledby="color-search-heading"
    >
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 rounded-full bg-gradient-to-r from-burnt-peach-400/50 via-pacific-blue-400/50 to-hunter-green-400/50" />
        <h2
          id="color-search-heading"
          className="text-xs sm:text-sm font-semibold tracking-wider uppercase text-deep-mocha-700 dark:text-deep-mocha-200"
        >
          Explore Butterflies by Color
        </h2>
        <span className="h-px flex-1 rounded-full bg-gradient-to-r from-burnt-peach-400/50 via-pacific-blue-400/50 to-hunter-green-400/50" />
      </div>

      <p className="mt-3 text-center text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
        Choose a color to run a live semantic search across the butterfly
        collection.
      </p>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {COLOR_OPTIONS.map((color) => {
          const isSelected = selectedColor === color.value;

          return (
            <button
              key={color.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => handleColorSearch(color.value)}
              className={`min-w-28 rounded-full px-6 py-2.5 text-sm font-semibold shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 ${color.className} ${
                isSelected
                  ? "ring-4 ring-deep-mocha-300/70 dark:ring-deep-mocha-500/70"
                  : "hover:-translate-y-0.5 hover:shadow-md"
              }`}
            >
              {color.label}
              {loading && isSelected ? "…" : ""}
            </button>
          );
        })}
      </div>

      <div className="mt-8 min-h-48" aria-busy={loading} aria-live="polite">
        {loading && selectedColor ? (
          <div className="flex justify-center py-8">
            <ImageLoading
              size={160}
              msg={`Finding ${selectedColor} butterflies`}
            />
          </div>
        ) : error ? (
          <p
            role="alert"
            className="mx-auto max-w-2xl rounded-lg border border-burnt-peach-200 bg-burnt-peach-50 px-4 py-3 text-center text-sm text-burnt-peach-700 dark:border-burnt-peach-800 dark:bg-burnt-peach-900/30 dark:text-burnt-peach-300"
          >
            {error}
          </p>
        ) : selectedColor && results.length === 0 ? (
          <p className="text-center text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
            No {selectedColor} butterfly matches were found. Try another color.
          </p>
        ) : selectedColor ? (
          <div>
            <p className="mb-5 text-center text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
              Showing {results.length} {selectedColor} butterfly
              {results.length === 1 ? "" : " matches"}, ordered from closest
              to least similar.
            </p>
            <div className="grid grid-cols-[repeat(auto-fit,160px)] justify-center gap-4">
              {results.map((result) => (
                <MLSearchResultCard key={result.imgId} data={result} />
              ))}
            </div>
          </div>
        ) : (
          <p className="text-center text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
            Select Red, Blue, or Green to see live search results.
          </p>
        )}
      </div>
    </section>
  );
}
