"use client";

import { useEffect, useRef, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import SpeciesTile from "@/components/SpeciesTile";
import { fetchThumbnailById } from "@/lib/images";
import { ColorSearchResult, searchByColor } from "@/lib/ml_search";
import { cleanSpeciesName, speciesUrlFromName } from "@/lib/names";

const RESULT_LIMIT = 6;
// The backend removes duplicate species after its vector lookup, so request a
// small candidate pool and then display the best six unique results.
const SEARCH_CANDIDATE_LIMIT = 12;

// Plain labels. The buttons used to paint themselves — colour gradients, an
// owl's eyes in radial gradients, diagonal stripes — which competed with the
// butterflies they were meant to introduce.
const SEARCH_OPTIONS = [
  { value: "red", label: "Red" },
  { value: "blue", label: "Blue" },
  { value: "green", label: "Green" },
  { value: "owl-like", label: "Owl-like" },
  { value: "striped", label: "Striped" },
] as const;

// Borrowed from the search-mode tabs above, so the two rows of pills on this
// page agree on what "selected" looks like.
const PILL_BASE =
  "border px-4 py-1.5 rounded-full text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-hunter-green-500 focus:ring-offset-2 dark:focus:ring-offset-deep-mocha-900";

// The tabs sit in one bordered container, which is what marks them as
// controls; these wrap, so each carries its own outline instead.
const PILL_IDLE =
  "border-deep-mocha-300 dark:border-deep-mocha-600 text-deep-mocha-700 dark:text-deep-mocha-300 hover:bg-deep-mocha-200/70 dark:hover:bg-deep-mocha-700/70";

const PILL_SELECTED =
  "border-transparent bg-hunter-green-200 dark:bg-hunter-green-900 text-deep-mocha-900 dark:text-hunter-green-50 shadow";

type SearchOptionValue = (typeof SEARCH_OPTIONS)[number]["value"];

/** One result, shown exactly as a featured butterfly is. */
function ColorSearchTile({ result }: { result: ColorSearchResult }) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void fetchThumbnailById(result.imgId)
      .then((url) => {
        if (!ignore) setThumbnailUrl(url);
      })
      .catch((error) =>
        console.error("Error fetching visual search thumbnail:", error),
      );
    return () => {
      ignore = true;
    };
  }, [result.imgId]);

  return (
    <SpeciesTile
      href={`/species/${speciesUrlFromName(result.species)}`}
      imageUrl={thumbnailUrl}
      label={cleanSpeciesName(result.species)}
      alt={`Image of ${result.species}`}
    />
  );
}

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
    <section className="w-full mt-16" aria-labelledby="visual-search-heading">
      <div className="w-full max-w-5xl mb-4 px-4 mx-auto">
        <h2
          id="visual-search-heading"
          className="text-2xl font-semibold text-center"
        >
          Explore by Appearance
        </h2>
      </div>

      <div className="mb-8 flex flex-wrap justify-center gap-3 px-4">
        {SEARCH_OPTIONS.map((option) => {
          const isSelected = selectedOption === option.value;

          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => handleOptionSearch(option.value)}
              className={`${PILL_BASE} ${isSelected ? PILL_SELECTED : PILL_IDLE}`}
            >
              {option.label}
              {loading && isSelected ? "…" : ""}
            </button>
          );
        })}
      </div>

      <div
        className={selectedOption ? "min-h-48" : ""}
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
          // The same grid the featured butterflies use, and no match
          // percentage: on a landing page the number invites a comparison
          // nobody came to make, and cosine distances read low even for a
          // good match.
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mx-auto">
            {results.map((result) => (
              <ColorSearchTile key={result.imgId} result={result} />
            ))}
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
