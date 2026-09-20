import type { ReactNode } from "react";

/** The gradient hairline that flanks every landing-page heading. */
const RULE =
  "h-px flex-1 rounded-full bg-gradient-to-r from-hunter-green-400/50 via-pacific-blue-400/50 to-frozen-water-400/50";

/**
 * The one heading treatment the landing page agrees on.
 *
 * The colour is the featured-butterflies green, promoted from that one
 * section to every section: the page used to pair it with a plain
 * `text-2xl font-semibold` heading elsewhere, which read as two pages
 * stacked rather than one.
 */
const HEADING =
  "text-xs sm:text-sm font-semibold tracking-wider uppercase text-hunter-green-600 dark:text-hunter-green-300 flex items-center gap-2";

/**
 * The width every landing-page section shares: readable on a phone, and
 * allowed to keep growing on a large monitor rather than stopping at the
 * 1024px the page used to cap itself at, which left a desktop screen mostly
 * empty on either side.
 */
export const LANDING_CONTAINER =
  "w-full mx-auto max-w-5xl lg:max-w-6xl xl:max-w-7xl 2xl:max-w-[88rem]";

/**
 * Both landing grids are the same grid; this is where they say so.
 *
 * Every step divides the six tiles each grid holds — 2, 3, then 6 across —
 * so a row is never left half-full the way the old four-column step left
 * the last two tiles stranded on a tablet.
 */
export const LANDING_GRID =
  "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-5 lg:gap-6";

export interface LandingSectionHeadingProps {
  title: string;
  /** Decorative only, so it is hidden from assistive technology. */
  emoji?: string;
  /** One line of sub-copy, centred beneath the rules. */
  description?: ReactNode;
  /** Set when the caller wires `aria-labelledby` to this heading. */
  id?: string;
  /** Spacing only, never colour. */
  className?: string;
}

/**
 * A landing-page section heading: two gradient rules, a small uppercase
 * green title, and optional sub-copy.
 *
 * Pure markup, so it carries no `"use client"` and can be used from both the
 * client tree and a server component.
 */
export default function LandingSectionHeading({
  title,
  emoji,
  description,
  id,
  className = "",
}: LandingSectionHeadingProps) {
  return (
    <div className={`${LANDING_CONTAINER} mb-4 ${className}`}>
      <div className="flex items-center gap-3">
        <span className={RULE} aria-hidden="true" />
        <h2 id={id} className={HEADING}>
          {emoji ? (
            <span className="text-lg" aria-hidden="true">
              {emoji}
            </span>
          ) : null}
          {title}
        </h2>
        <span className={RULE} aria-hidden="true" />
      </div>
      {description ? (
        <p className="mt-3 text-center text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
          {description}
        </p>
      ) : null}
    </div>
  );
}
