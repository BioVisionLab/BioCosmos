import Link from "next/link";

import { COL_RANK_ORDER, ITALIC_COL_RANKS, rankValue } from "@/lib/colTaxonomy";
import { TaxonomyData } from "@/lib/speciesData";
import { familyHref, genusHref, orderHref } from "@/lib/taxonSlug";

// Each rank sits one step right of its parent.
const STEP_REM = 0.875;

// The elbow from the parent's step down into this one, drawn as a
// pseudo-element so it never reaches the accessibility tree.
const ELBOW =
  "before:absolute before:-left-[0.625rem] before:-top-[0.55rem] " +
  "before:h-[1.45rem] before:w-2 before:rounded-bl before:border-l before:border-b " +
  "before:border-deep-mocha-300 dark:before:border-deep-mocha-600";

const RANK_TAG =
  "shrink-0 text-[0.625rem] uppercase tracking-wider font-semibold " +
  "text-hunter-green-700/80 dark:text-hunter-green-400/80";

function rankHref(rank: string, value: string): string | null {
  if (rank === "order") return orderHref(value);
  if (rank === "family") return familyHref(value);
  if (rank === "genus") return genusHref(value);
  return null;
}

/**
 * The lineage from kingdom down to the species, one rung per rank.
 *
 * Only ranks Catalogue of Life populates appear: an intermediate rank with no
 * value would be a rung reading "Unknown", which says nothing about the taxon.
 */
export function ClassificationLadder({
  taxonomy,
}: {
  taxonomy: TaxonomyData | null;
}) {
  if (!taxonomy) {
    return (
      <p className="text-deep-mocha-500 dark:text-deep-mocha-400">
        No classification data available.
      </p>
    );
  }

  const rungs = COL_RANK_ORDER.map((rank) => ({
    rank,
    value: rankValue(taxonomy, rank),
  })).filter(
    (rung): rung is { rank: (typeof COL_RANK_ORDER)[number]; value: string } =>
      !!rung.value,
  );
  const last = rungs.length - 1;

  return (
    // A full lineage is wider than a phone. There, rather than squeezing the
    // steps or wrapping names, the ladder keeps its shape and scrolls sideways
    // inside its own box, so the page itself never does. From `sm` up there is
    // room enough that names wrap within the column instead.
    <div className="overflow-x-auto sm:overflow-visible -mx-1 px-1 pb-1 sm:pb-0">
      <ol
        aria-label="Classification"
        className="list-none m-0 p-0 w-max min-w-full sm:w-auto"
      >
        {rungs.map(({ rank, value }, index) => {
          const isSpecies = index === last && rank === "species";
          const href = isSpecies ? null : rankHref(rank, value);
          const name = ITALIC_COL_RANKS.has(rank) ? (
            <i className="italic">{value}</i>
          ) : (
            value
          );

          return (
            <li
              key={rank}
              className={`relative flex items-baseline gap-2 py-1 whitespace-nowrap sm:whitespace-normal ${index > 0 ? ELBOW : ""}`}
              style={{ marginLeft: `${index * STEP_REM}rem` }}
            >
              <span className={RANK_TAG}>{rank}</span>
              <span className="min-w-0 wrap-break-words">
                <span
                  className={
                    isSpecies
                      ? "rounded-md px-2 py-0.5 box-decoration-clone bg-gradient-to-r from-hunter-green-500/20 to-pacific-blue-500/20 font-semibold text-deep-mocha-900 dark:text-deep-mocha-50"
                      : ""
                  }
                >
                  {href ? (
                    <Link
                      href={href}
                      className="hover:underline text-pacific-blue-700 dark:text-pacific-blue-300"
                    >
                      {name}
                    </Link>
                  ) : (
                    name
                  )}
                </span>
                {isSpecies && taxonomy.authorship ? (
                  <span className="ml-1.5 sm:ml-0 sm:mt-0.5 sm:block text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
                    {taxonomy.authorship}
                  </span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
