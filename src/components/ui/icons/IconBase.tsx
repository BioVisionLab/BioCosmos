import type { CSSProperties, ReactNode } from "react";

export interface IconProps {
  /** Sizing and spacing only — colour is the primitive's job. */
  className?: string;
  /**
   * Stroke width in viewBox units on the 24-grid.
   *
   * A viewBox stroke scales with the icon, so the same value reads heavier the
   * larger the icon is drawn. Pass a thinner one at the 80px call sites; do
   * not reach for `vector-effect="non-scaling-stroke"`, which pins the stroke
   * to device pixels and makes the large icons look unrelated to the small
   * ones.
   */
  strokeWidth?: number;
  /** Accessible name. Omitted, the icon is decorative and hidden. */
  title?: string;
}

/**
 * Three stroke weights, not one.
 *
 * The outline of a subject, the detail drawn inside it, and the context behind
 * it are three different kinds of line, and drawing all three at one weight is
 * what turned a leaf's venation into a net and buried a chrysalis's wing-case
 * ridge in its own silhouette. Detail is roughly two thirds the outline, which
 * is enough for it to recede at 48px and still resolve at 80px.
 *
 * The supporting tone is thinner as well as differently coloured, so the
 * hierarchy survives `forced-colors` mode and the `currentColor` fallback,
 * where both hues collapse to one.
 */
const SECONDARY_RATIO = 0.8;
const DETAIL_RATIO = 0.62;

/**
 * Every domain icon in the app.
 *
 * One 24-grid, one stroke weight, one palette. Icons supply nothing but their
 * geometry, which is what keeps each of them a few hundred bytes instead of
 * the 1–12 KB the stock silhouettes they replaced carried.
 *
 * The grid matches the heroicons-style chrome already inline elsewhere in the
 * app and lucide's, so these sit correctly beside `ChevronRight` and friends.
 *
 * Geometry passed as `secondary` is drawn first, and therefore behind: it is
 * the context a subject is measured against or sits on — substrate, scale,
 * axis — never the subject itself. That single rule is what makes the set read
 * as one system rather than as eighteen drawings.
 */
export function IconBase({
  className,
  strokeWidth = 1.75,
  title,
  secondary,
  children,
}: IconProps & { secondary?: ReactNode; children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      stroke="var(--bc-icon-primary, currentColor)"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      className={`bc-icon ${className ?? ""}`}
      // Published as custom properties so `Detail` can be dropped in anywhere
      // inside an icon without every icon having to thread `strokeWidth`
      // through to it.
      style={
        {
          "--bc-sw-detail": strokeWidth * DETAIL_RATIO,
          "--bc-sw-secondary": strokeWidth * SECONDARY_RATIO,
        } as CSSProperties
      }
    >
      {title ? <title>{title}</title> : null}
      {secondary ? (
        <g
          data-part="secondary"
          stroke="var(--bc-icon-secondary, currentColor)"
          strokeWidth="var(--bc-sw-secondary)"
        >
          {secondary}
        </g>
      ) : null}
      {children}
    </svg>
  );
}

/**
 * Interior detail, in the subject's colour at the lighter weight: venation,
 * ribbing, segment divisions, base-pair rungs, chevrons.
 *
 * The test for whether a line belongs here is whether removing it would change
 * what the icon depicts. A leaf without its veins is still a leaf; a leaf
 * without its outline is nothing.
 */
export function Detail({ children }: { children: ReactNode }) {
  return (
    <g data-part="detail" strokeWidth="var(--bc-sw-detail)">
      {children}
    </g>
  );
}

/** A filled marker — a club, an eye, a hub. Rare, and always the subject. */
export function Dot({ cx, cy, r = 0.8 }: { cx: number; cy: number; r?: number }) {
  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill="var(--bc-icon-primary, currentColor)"
      stroke="none"
    />
  );
}
