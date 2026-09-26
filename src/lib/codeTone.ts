/**
 * The badge palette, shared by every status hint.
 *
 * Lives apart from any one vocabulary because both the Catalogue of Life
 * taxonomy status and the GADM coordinate status render through it, and the
 * two should never drift into different colours for the same kind of claim.
 */

export type CodeTone =
  "matched" | "ambiguous" | "unmatched" | "invalid" | "neutral";

/**
 * Deliberately not the green/red of a conservation status: burnt peach reads
 * as "needs a look" and mocha as "absent", rather than as good or bad.
 *
 * `invalid` is the heavier peach, and only for data that is wrong rather than
 * merely unresolved — a coordinate of 0,0 or a latitude past the pole is not
 * a judgement call the way a country disagreement is.
 */
const TONE_CLASSES: Record<CodeTone, string> = {
  matched:
    "bg-hunter-green-100 text-hunter-green-800 dark:bg-hunter-green-900/60 dark:text-hunter-green-200 hover:bg-hunter-green-200 dark:hover:bg-hunter-green-900",
  ambiguous:
    "bg-burnt-peach-100 text-burnt-peach-800 dark:bg-burnt-peach-900/60 dark:text-burnt-peach-200 hover:bg-burnt-peach-200 dark:hover:bg-burnt-peach-900",
  invalid:
    "bg-burnt-peach-200 text-burnt-peach-900 dark:bg-burnt-peach-800/70 dark:text-burnt-peach-100 hover:bg-burnt-peach-300 dark:hover:bg-burnt-peach-800",
  unmatched:
    "bg-deep-mocha-200 text-deep-mocha-800 dark:bg-deep-mocha-800 dark:text-deep-mocha-200 hover:bg-deep-mocha-300 dark:hover:bg-deep-mocha-700",
  neutral:
    "bg-pacific-blue-100/70 text-pacific-blue-800 dark:bg-pacific-blue-900/50 dark:text-pacific-blue-200 hover:bg-pacific-blue-200/70 dark:hover:bg-pacific-blue-900",
};

export function toneClasses(tone: CodeTone): string {
  return TONE_CLASSES[tone];
}
