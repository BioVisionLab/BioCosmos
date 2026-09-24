"use client";

import { useEffect, useState } from "react";
import SpecimenCell from "@/components/SpecimenCell";
import LandingSectionHeading, {
  LANDING_CONTAINER,
} from "@/components/LandingSection";
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
// candidate pool and then display the best six unique results. Twelve was
// too few: "yellow" collapsed to four species, dominated by a handful of
// well-photographed pierids, and left two cells empty. Twenty-four fills all
// six for every option.
const SEARCH_CANDIDATE_LIMIT = 24;

// Each label carries one small swatch of what it searches for. The buttons
// once painted themselves edge to edge — gradients, an owl's eyes, stripes —
// which competed with the butterflies they introduce; a 14px chip says the
// same thing and leaves the colour to the results.
//
// Patterns lead, then colours: the pattern searches are the ones worth
// discovering, and a colour name reads as an ordinary filter beside them.
const SEARCH_OPTIONS = [
  {
    value: "striped",
    label: "Striped",
    swatch: "repeating-linear-gradient(135deg, #3b2a1a 0 3px, #e8c98a 3px 6px)",
  },
  {
    value: "owl-like",
    label: "Owl-like",
    swatch:
      "radial-gradient(circle, #1c1717 0 2px, #f0e2b8 2px 4px, #8a5a2b 4px)",
  },
  { value: "red", label: "Red", swatch: "#c8452a" },
  { value: "blue", label: "Blue", swatch: "#2b64b8" },
  { value: "green", label: "Green", swatch: "#5fc39a" },
  { value: "yellow", label: "Yellow", swatch: "#e8c33a" },
] as const;

// One bordered strip of segments, the selected one raised onto the surface
// with a green underline, so the control reads as a single switch rather
// than six loose buttons.
const SEGMENT =
  "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-r last:border-r-0 border-deep-mocha-200 dark:border-deep-mocha-700 focus-visible:relative focus-visible:z-10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-hunter-green-500";

const SEGMENT_IDLE =
  "bg-white/70 text-deep-mocha-600 hover:bg-deep-mocha-50 hover:text-deep-mocha-900 dark:bg-deep-mocha-900/60 dark:text-deep-mocha-300 dark:hover:bg-deep-mocha-800 dark:hover:text-deep-mocha-50";

const SEGMENT_SELECTED =
  "bg-deep-mocha-50 text-deep-mocha-900 shadow-[inset_0_-2px_0_var(--color-hunter-green-600)] dark:bg-deep-mocha-800 dark:text-deep-mocha-50 dark:shadow-[inset_0_-2px_0_var(--color-hunter-green-300)]";

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
    <section className="w-full mt-20" aria-labelledby="visual-search-heading">
      <LandingSectionHeading
        id="visual-search-heading"
        eyebrow="Visual search"
        title="Explore by appearance"
        description="Pick a colour or pattern. Results are ranked by image similarity. You can use semantic search for more complex queries."
      />

      <div className={LANDING_CONTAINER}>
        <div
          role="group"
          aria-label="Appearance"
          className="bc-reveal flex max-w-full flex-wrap overflow-hidden rounded-2xl border border-deep-mocha-200 w-fit dark:border-deep-mocha-700"
        >
          {SEARCH_OPTIONS.map((option) => {
            const isSelected = selectedOption === option.value;

            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={isSelected}
                aria-busy={loading && isSelected}
                onClick={() => handleSelect(option.value)}
                className={`${SEGMENT} ${isSelected ? SEGMENT_SELECTED : SEGMENT_IDLE}`}
              >
                <span
                  aria-hidden="true"
                  className="h-3.5 w-3.5 shrink-0 rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.12)]"
                  style={{ background: option.swatch }}
                />
                {option.label}
                {/* A permanently reserved slot. The ellipsis used to be
                    appended to the label, so the segment grew mid-request
                    and reflowed the whole row. */}
                <span
                  aria-hidden="true"
                  className="-ml-1 inline-block w-3 overflow-hidden text-left"
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
          className={`mt-3 mb-4 h-5 max-w-3xl truncate text-sm ${
            error
              ? "text-burnt-peach-600 dark:text-burnt-peach-400"
              : "text-deep-mocha-500 dark:text-deep-mocha-400"
          }`}
        >
          {statusMessage}
        </p>

        {/* Six compartments, always: the tray is the same height from first
            paint, the cells stay mounted across searches, and the previous
            results stay legible while the next ones load rather than being
            torn down and rebuilt. */}
        <ul
          aria-busy={loading}
          className={`bc-reveal m-0 grid list-none grid-cols-2 gap-px overflow-hidden rounded-2xl border border-deep-mocha-200 bg-deep-mocha-200 p-0 transition-opacity duration-200 sm:grid-cols-3 lg:grid-cols-6 dark:border-deep-mocha-700 dark:bg-deep-mocha-700 ${
            loading ? "opacity-60" : "opacity-100"
          }`}
        >
          {Array.from({ length: RESULT_LIMIT }, (_, slot) => {
            const result = results[slot] ?? null;
            const name = result
              ? toBinomialName(cleanSpeciesName(result.species))
              : "";
            return (
              // Keyed by position, not by image id: switching colour should
              // swap the contents of six cells that stay put, not unmount six
              // and mount six more.
              <li key={`slot-${slot}`} className="flex">
                <SpecimenCell
                  // A record identified only to genus has no species page, so
                  // the cell shows the image without pretending to lead
                  // anywhere.
                  href={
                    result && isSpeciesName(result.species)
                      ? `/species/${speciesUrlFromName(result.species)}`
                      : null
                  }
                  imageUrl={result ? imageUrlById(result.imgId, "full") : null}
                  label={name}
                  alt={result ? `Image of ${name}` : ""}
                  index={slot}
                  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 17vw"
                />
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
