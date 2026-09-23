"use client";

import { useEffect, useState } from "react";
import SpeciesTile from "@/components/SpeciesTile";
import LandingSectionHeading, {
  LANDING_CONTAINER,
  LANDING_GRID,
} from "@/components/LandingSection";
import { AppearanceIcon } from "@/components/ui/icons";
import { imageUrlById } from "@/lib/images";
import { ColorSearchResult, searchByColor } from "@/lib/ml_search";
import {
  cleanSpeciesName,
  isSpeciesName,
  speciesUrlFromName,
  toBinomialName,
} from "@/lib/names";

const RESULT_LIMIT = 6;
// The backend removes duplicate species after its vector lookup, so request a
// small candidate pool and then display the best six unique results.
const SEARCH_CANDIDATE_LIMIT = 12;

// Plain labels. The buttons used to paint themselves — colour gradients, an
// owl's eyes in radial gradients, diagonal stripes — which competed with the
// butterflies they were meant to introduce.
//
// Patterns lead, then colours: the pattern searches are the ones worth
// discovering, and a colour name reads as an ordinary filter beside them.
const SEARCH_OPTIONS = [
  { value: "striped", label: "Striped" },
  { value: "owl-like", label: "Owl-like" },
  { value: "red", label: "Red" },
  { value: "blue", label: "Blue" },
  { value: "green", label: "Green" },
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

// The section opens on a search rather than on six empty slots: a grid of
// butterflies shows what the control does, where "pick an option" only
// described it. Stripes are the clearest demonstration of the pattern
// search, so they are the ones that run.
const DEFAULT_OPTION: SearchOptionValue = "striped";

export default function ColorSearch() {
  const [selectedOption, setSelectedOption] =
    useState<SearchOptionValue>(DEFAULT_OPTION);
  const [results, setResults] = useState<ColorSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Picking an option is the only way to start a search, so the pending
  // state belongs to the click — and to the initial `loading` value, which
  // covers the default search that runs on mount.
  const handleSelect = (option: SearchOptionValue) => {
    if (option === selectedOption) return;
    setSelectedOption(option);
    setError(null);
    setLoading(true);
  };

  // The selection drives the request, rather than the click handler doing
  // so: the default option then searches on mount through the same path as
  // every later click, and React's cleanup — not a request counter — is
  // what discards a superseded response.
  useEffect(() => {
    const controller = new AbortController();
    let current = true;

    const run = async () => {
      try {
        const searchResults = await searchByColor(
          selectedOption,
          SEARCH_CANDIDATE_LIMIT,
          controller.signal,
        );
        if (current) setResults(searchResults.slice(0, RESULT_LIMIT));
      } catch (searchError) {
        if (!current || controller.signal.aborted) return;
        setResults([]);
        setError(
          searchError instanceof Error
            ? searchError.message
            : "An unexpected error occurred during visual search.",
        );
      } finally {
        if (current) setLoading(false);
      }
    };

    run();

    return () => {
      current = false;
      controller.abort();
    };
  }, [selectedOption]);

  const selectedLabel = SEARCH_OPTIONS.find(
    (option) => option.value === selectedOption,
  )?.label;

  // Every outcome — searching, failed, found nothing — is one line in one
  // place. They used to be three differently sized blocks that replaced each
  // other, so the grid below moved every time the state changed.
  const statusMessage = error
    ? error
    : loading
      ? `Finding ${selectedLabel ?? selectedOption} butterflies…`
      : results.length === 0
        ? `No ${selectedLabel ?? selectedOption} butterfly matches were found. Try another option.`
        : " ";

  return (
    <section className="w-full mt-16" aria-labelledby="visual-search-heading">
      <LandingSectionHeading
        id="visual-search-heading"
        icon={<AppearanceIcon />}
        title="Explore by Appearance"
        description="Pick a colour or pattern to preview matching butterflies."
      />

      <div className="mb-4 flex flex-wrap justify-center gap-2 sm:gap-3">
        {SEARCH_OPTIONS.map((option) => {
          const isSelected = selectedOption === option.value;

          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              aria-busy={loading && isSelected}
              onClick={() => handleSelect(option.value)}
              className={`${PILL_BASE} ${isSelected ? PILL_SELECTED : PILL_IDLE}`}
            >
              {option.label}
              {/* A permanently reserved slot. The ellipsis used to be
                  appended to the label, so the pill grew mid-request and
                  reflowed the whole wrapped row. */}
              <span
                aria-hidden="true"
                className="inline-block w-3 overflow-hidden text-left align-middle"
              >
                {loading && isSelected ? "…" : ""}
              </span>
            </button>
          );
        })}
      </div>

      <p
        role={error ? "alert" : "status"}
        aria-live="polite"
        className={`mx-auto mb-6 h-5 max-w-3xl truncate text-center text-sm ${
          error
            ? "text-burnt-peach-600 dark:text-burnt-peach-400"
            : "text-deep-mocha-500 dark:text-deep-mocha-400"
        }`}
      >
        {statusMessage}
      </p>

      {/* Six slots, always. The grid is the same height from first paint and
          never changes, the tiles stay mounted across searches, and the
          previous results stay legible while the next ones load rather than
          being torn down and rebuilt. */}
      <div
        aria-busy={loading}
        className={`${LANDING_GRID} ${LANDING_CONTAINER} transition-opacity duration-200 ${
          loading ? "opacity-60" : "opacity-100"
        }`}
      >
        {Array.from({ length: RESULT_LIMIT }, (_, slot) => {
          const result = results[slot] ?? null;
          return (
            <SpeciesTile
              // Keyed by position, not by image id: switching colour should
              // swap the contents of six tiles that stay put, not unmount
              // six and mount six more.
              key={`slot-${slot}`}
              // A record identified only to genus has no species page, so the
              // tile shows the image without pretending to lead anywhere.
              href={
                result && isSpeciesName(result.species)
                  ? `/species/${speciesUrlFromName(result.species)}`
                  : "#"
              }
              imageUrl={result ? imageUrlById(result.imgId, "full") : null}
              label={
                result ? toBinomialName(cleanSpeciesName(result.species)) : ""
              }
              alt={result ? `Image of ${result.species}` : ""}
              placeholder={loading ? "spinner" : "empty"}
            />
          );
        })}
      </div>
    </section>
  );
}
