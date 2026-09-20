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

/** Both landing grids are the same grid; this is where they say so. */
export const LANDING_GRID =
  "grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mx-auto";

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
    <div className={`w-full max-w-5xl mb-4 px-4 mx-auto ${className}`}>
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
