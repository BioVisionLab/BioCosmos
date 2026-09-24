import type { ReactNode } from "react";

/**
 * The one heading treatment the landing page agrees on: a small mono eyebrow
 * naming what kind of section this is, then the title, then one line of
 * sub-copy.
 *
 * The eyebrow is the label a drawer tag would carry, in the same face as the
 * specimen labels in the hero tray, so the sections below read as parts of
 * the same collection rather than as a stack of widgets. It replaced an icon
 * and a gradient rule running out to the right, which put the same ornament
 * on every section and so said nothing about any of them.
 */
export const LANDING_EYEBROW =
  "font-label text-xs font-medium uppercase tracking-[0.08em] text-deep-mocha-500 dark:text-deep-mocha-400";

const HEADING =
  "font-display text-2xl sm:text-3xl font-semibold tracking-tight text-balance text-deep-mocha-900 dark:text-deep-mocha-50";

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
  /** What kind of section this is, set small above the title. */
  eyebrow?: string;
  /** One line of sub-copy, beneath the title. */
  description?: ReactNode;
  /** Set when the caller wires `aria-labelledby` to this heading. */
  id?: string;
  /** Spacing only, never colour. */
  className?: string;
  /**
   * Whether the heading sets its own column width. Off when the caller has
   * already placed it in a column, beside other content.
   */
  contained?: boolean;
}

/**
 * A landing-page section heading: eyebrow, title and optional sub-copy, flush
 * left on the shared column.
 *
 * Left-aligned rather than centred: a centred title has to be found before
 * it can be read, and the sections below it are left-aligned too.
 *
 * Pure markup, so it carries no `"use client"` and can be used from both the
 * client tree and a server component.
 */
export default function LandingSectionHeading({
  title,
  eyebrow,
  description,
  id,
  className = "",
  contained = true,
}: LandingSectionHeadingProps) {
  return (
    <div className={`${contained ? LANDING_CONTAINER : ""} mb-6 ${className}`}>
      {eyebrow ? <p className={`${LANDING_EYEBROW} mb-2`}>{eyebrow}</p> : null}
      <h2 id={id} className={HEADING}>
        {title}
      </h2>
      {description ? (
        <p className="mt-2 max-w-6xl text-sm sm:text-base text-deep-mocha-600 dark:text-deep-mocha-400">
          {description}
        </p>
      ) : null}
    </div>
  );
}
