import type { CountryDiversityRow } from "@/lib/countryDiversity";

/**
 * The stepped colour scale for species per country.
 *
 * One hue (the site's hunter green), light to dark in light mode and flipped
 * in dark mode so "more" always reads as "more contrast with the surface".
 * Steps are 1-2-5 log breaks: a handful of countries hold hundreds of species
 * and most hold a few, so a linear scale would paint nearly every country the
 * lightest step, which is what the notebook's linear viridis does at print
 * size and what a reader cannot hover their way out of on the web.
 */
export interface SpeciesScale {
  /** Lower bound of each step; the first is always 1. */
  breaks: number[];
  colors: string[];
  noData: string;
}

const LIGHT_RAMP = [
  "#c0deba", // hunter-green-200
  "#a1ce97", // 300
  "#82be74", // 400
  "#4f8b41", // 600
  "#3b6831", // 700
  "#274521", // 800
];
const DARK_RAMP = [
  "#3b6831", // hunter-green-700
  "#4f8b41", // 600
  "#62ad52", // 500
  "#82be74", // 400
  "#a1ce97", // 300
  "#d0e7cb", // between 100 and 200
];
const NO_DATA_LIGHT = "#e7e5e4";
const NO_DATA_DARK = "#44403c";
const MAX_STEPS = LIGHT_RAMP.length;

function niceBreaks(max: number): number[] {
  const candidates: number[] = [];
  for (let magnitude = 1; magnitude <= Math.max(max, 1); magnitude *= 10) {
    for (const multiple of [1, 2, 5]) {
      const value = multiple * magnitude;
      if (value <= max) candidates.push(value);
    }
  }
  if (candidates.length <= MAX_STEPS) return candidates;
  // Keep 1 and spread the rest evenly across the log range.
  const picked = new Set<number>();
  for (let step = 0; step < MAX_STEPS; step++) {
    const index = Math.round((step * (candidates.length - 1)) / MAX_STEPS);
    picked.add(candidates[index]);
  }
  return [...picked].sort((a, b) => a - b);
}

export function speciesScale(
  rows: CountryDiversityRow[],
  isDark: boolean,
): SpeciesScale {
  const max = rows.reduce((top, row) => Math.max(top, row.speciesCount), 1);
  const breaks = niceBreaks(max);
  const ramp = isDark ? DARK_RAMP : LIGHT_RAMP;
  // Fewer steps than colours: take them from the dark end, so the richest
  // country always wears the strongest colour.
  const colors = breaks.map(
    (_, index) => ramp[ramp.length - breaks.length + index],
  );
  return { breaks, colors, noData: isDark ? NO_DATA_DARK : NO_DATA_LIGHT };
}

/** "1–4", "5–9", …, "500+" for the legend. */
export function stepLabels(breaks: number[]): string[] {
  return breaks.map((lower, index) => {
    const next = breaks[index + 1];
    if (next === undefined) return `${lower.toLocaleString("en-US")}+`;
    return next - 1 === lower
      ? lower.toLocaleString("en-US")
      : `${lower.toLocaleString("en-US")}–${(next - 1).toLocaleString("en-US")}`;
  });
}
