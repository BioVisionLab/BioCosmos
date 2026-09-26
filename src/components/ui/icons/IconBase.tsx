import type { CSSProperties, ReactNode } from "react";

/**
 * How large the icon is drawn, which sets its stroke.
 *
 * - `sm`: inline with text, 16–32px — the landing-page section marks.
 * - `md`: a trait or data card, around 48px. The default.
 * - `lg`: a hero glyph, 64–96px — the key-trait and specimen panels.
 */
export type IconSize = "sm" | "md" | "lg";

/**
 * Three stroke weights, one per size tier, in viewBox units on the 24-grid.
 *
 * A viewBox stroke scales with the icon, so one value reads hairline at 24px
 * and heavy at 80px. Before these tiers every large call site picked its own
 * number (1.1, 1.2) and the set drifted; now a call site says only which tier
 * it is, and the weights are set once, here. Rendered, they come out at about
 * 1.75px at 24, 3px at 48 and 3.5px at 80: heavier as the icon grows, but
 * slower than the icon does, which is what keeps a small mark legible and a
 * large one from turning into a stencil.
 *
 * Do not reach for `vector-effect="non-scaling-stroke"` instead: it pins the
 * stroke to device pixels and makes the large icons look unrelated to the
 * small ones.
 */
const STROKE_BY_SIZE: Record<IconSize, number> = {
  sm: 1.75,
  md: 1.5,
  lg: 1.05,
};

export interface IconProps {
  /** Sizing and spacing only — colour is the primitive's job. */
  className?: string;
  /** The size tier the icon is drawn at. Picks the stroke; see `IconSize`. */
  size?: IconSize;
  /** Accessible name. Omitted, the icon is decorative and hidden. */
  title?: string;
}

/**
 * Inside each tier, three stroke weights by role, not one.
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
 * The dash pattern, derived from the stroke rather than written per path.
 *
 * `strokeLinecap="round"` extends every dash by half a stroke at *each* end,
 * which the hand-written `strokeDasharray="1.6 1.5"` these replace did not
 * account for: at stroke 1.75 each dash rendered 3.35 long on a 3.10 period,
 * so the dashes overlapped and every dashed path in the set drew as a solid
 * line. The "not established" signal it was carrying had been invisible for as
 * long as it has existed.
 *
 * Deriving both numbers from the stroke is what keeps that from coming back
 * the next time the weight moves: the gap is 1.75 - 1 = 0.75 of a stroke wide
 * whatever the stroke is.
 */
const DASH_ON_RATIO = 0.75;
const DASH_OFF_RATIO = 1.75;

/**
 * Every domain icon in the app.
 *
 * One 24-grid, three stroke tiers, one palette. Icons supply nothing but their
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
  size = "md",
  title,
  secondary,
  children,
}: IconProps & { secondary?: ReactNode; children: ReactNode }) {
  const strokeWidth = STROKE_BY_SIZE[size];
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
          "--bc-dash": `${strokeWidth * DASH_ON_RATIO} ${strokeWidth * DASH_OFF_RATIO}`,
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

/**
 * Spread onto a path that means "not established" or "no data".
 *
 * A style object rather than a `strokeDasharray` attribute, and that is not
 * cosmetic: `var()` does not resolve inside an SVG presentation attribute, so
 * `strokeDasharray="var(--bc-dash)"` silently renders solid -- which looks
 * exactly like the bug this replaces. It has to go through the CSS property.
 */
export const DASHED: CSSProperties = { strokeDasharray: "var(--bc-dash)" };

/** A filled marker — a club, an eye, a hub. Rare, and always the subject. */
export function Dot({
  cx,
  cy,
  r = 0.8,
}: {
  cx: number;
  cy: number;
  r?: number;
}) {
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
