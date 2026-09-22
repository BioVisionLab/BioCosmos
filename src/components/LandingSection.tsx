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
 *
 * Sized as a heading rather than as a label. The old `text-xs` uppercase
 * treatment was smaller than the body copy underneath it, so the sections it
 * titled read as unlabelled.
 */
const HEADING =
  "text-xl sm:text-2xl font-semibold text-hunter-green-600 dark:text-hunter-green-300 flex items-center gap-2 shrink-0";

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
  /**
   * The section's mark, drawn from the same two-tone set the species pages
   * use. Decorative, so it carries no accessible name.
   *
   * This replaced a literal emoji, which rendered as a different drawing on
   * every platform and could not follow the theme.
   */
  icon?: ReactNode;
  /** One line of sub-copy, beneath the title. */
  description?: ReactNode;
  /** Set when the caller wires `aria-labelledby` to this heading. */
  id?: string;
  /** Spacing only, never colour. */
  className?: string;
}

/**
 * A landing-page section heading: a green title flush left, one gradient rule
 * running out to the right, and optional sub-copy beneath it.
 *
 * Left-aligned rather than centred between two rules. A centred title has to
 * be found before it can be read, and on a narrow screen it wrapped while the
 * rules stayed vertically centred, which drew them straight through the
 * second line.
 *
 * Pure markup, so it carries no `"use client"` and can be used from both the
 * client tree and a server component.
 */
export default function LandingSectionHeading({
  title,
  icon,
  description,
  id,
  className = "",
}: LandingSectionHeadingProps) {
  return (
    <div className={`${LANDING_CONTAINER} mb-4 ${className}`}>
      <div className="flex items-center gap-3">
        <h2 id={id} className={HEADING}>
          {icon ? (
            <span
              className="h-6 w-6 sm:h-7 sm:w-7 shrink-0 [&>svg]:h-full [&>svg]:w-full"
              aria-hidden="true"
            >
              {icon}
            </span>
          ) : null}
          {title}
        </h2>
        <span className={RULE} aria-hidden="true" />
      </div>
      {description ? (
        <p className="mt-3 text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
          {description}
        </p>
      ) : null}
    </div>
  );
}
