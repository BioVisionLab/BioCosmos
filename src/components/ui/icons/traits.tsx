import type { ReactNode } from "react";

import type {
  DiapauseCode,
  OvipositionCode,
  VoltinismCode,
} from "@/lib/leptraits";

import { DASHED, Detail, Dot, IconBase, type IconProps } from "./IconBase";

// ---------------------------------------------------------------------------
// The year ring
//
// Phenology is cyclic, so the three icons that describe it share one
// construct: a ring with twelve month ticks, January at twelve o'clock and its
// tick drawn longer as an index mark. A twelve-cell linear strip would give
// each month two grid units against a 1.4 stroke and merge into mush; on the
// ring each month is over four units of arc.
//
// The ring is always secondary. What sits on it is always the subject.
// ---------------------------------------------------------------------------

const RING_R = 6.6;

/** Degrees clockwise from January at the top, to a point on the 24-grid. */
function ringPoint(deg: number, r: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [12 + r * Math.cos(rad), 12 + r * Math.sin(rad)];
}

function p(deg: number, r: number): string {
  const [x, y] = ringPoint(deg, r);
  return `${x.toFixed(2)} ${y.toFixed(2)}`;
}

/**
 * The ring, plus a single index mark at January.
 *
 * Twelve month ticks were the obvious thing to draw and had to go: at 48px a
 * ring of twelve short radials reads unmistakably as a gear, and every icon
 * built on it inherited that. The ring alone carries "a year"; what sits on it
 * carries the rest.
 */
function YearRing() {
  return (
    <>
      <circle cx="12" cy="12" r={RING_R} />
      <path d={`M${p(0, RING_R - 1.4)}L${p(0, RING_R + 1.4)}`} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Morphology
// ---------------------------------------------------------------------------

/**
 * Wingspan.
 *
 * The butterfly is drawn in the set position, as on a spreading board, and the
 * dimension line below runs apex to apex — which is how a wingspan is actually
 * measured. Without the dimension line this would just be a butterfly; the
 * extension lines dropping from the forewing apices are what make it the
 * measurement.
 */
export function WingspanIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M3.6 20.2H20.4" />
          <path d="M5.4 18.8L3.6 20.2L5.4 21.6" />
          <path d="M18.6 18.8L20.4 20.2L18.6 21.6" />
        </>
      }
    >
      <path d="M12 7.2C9 5.4 6 4.2 3.6 4.7C2.6 6.9 3.4 9.4 5.4 10.9C7.6 11.1 10 10.8 12 10.6Z" />
      <path d="M12 7.2C15 5.4 18 4.2 20.4 4.7C21.4 6.9 20.6 9.4 18.6 10.9C16.4 11.1 14 10.8 12 10.6Z" />
      <path d="M12 12.6C9.8 13 7.2 13.6 5.9 14.9C5.3 16.5 6.7 18 8.8 18.2C10.3 17.4 11.4 15.8 12 14.3Z" />
      <path d="M12 12.6C14.2 13 16.8 13.6 18.1 14.9C18.7 16.5 17.3 18 15.2 18.2C13.7 17.4 12.6 15.8 12 14.3Z" />
      <path d="M12 6.2V17.2" />
      <Detail>
        <path d="M11.7 6.2C10.7 4.6 9.5 3.7 8.3 3.2" />
        <path d="M12.3 6.2C13.3 4.6 14.5 3.7 15.7 3.2" />
        <path d="M11 8C9.3 7.8 7.4 7.6 5.6 7.8" />
        <path d="M13 8C14.7 7.8 16.6 7.6 18.4 7.8" />
        <path d="M10.4 14.4C9.2 14.8 8.2 15.4 7.6 16.1" />
        <path d="M13.6 14.4C14.8 14.8 15.8 15.4 16.4 16.1" />
      </Detail>
      <Dot cx={8.1} cy={3.1} r={0.6} />
      <Dot cx={15.9} cy={3.1} r={0.6} />
    </IconBase>
  );
}

// ---------------------------------------------------------------------------
// Phenology
// ---------------------------------------------------------------------------

/**
 * Flight duration.
 *
 * The datum is a count of months, not flight behaviour — a flying butterfly
 * says nothing about how long a season lasts. A highlighted arc read against
 * the full year does, and the caliper outside it says the arc is a measured
 * span rather than a highlight.
 */
export function FlightDurationIcon(props: IconProps) {
  return (
    <IconBase {...props} secondary={<YearRing />}>
      <path d={`M${p(10, 9.6)}L${p(10, 7.6)}`} />
      <path d={`M${p(140, 9.6)}L${p(140, 7.6)}`} />
      <path d={`M${p(10, 9.6)}A9.6 9.6 0 0 1 ${p(140, 9.6)}`} />
    </IconBase>
  );
}

/** One generation peak, rising outward from the ring. */
function peak(deg: number, key: number, dashed = false) {
  return (
    <path
      key={key}
      style={dashed ? DASHED : undefined}
      d={`M${p(deg - 17, RING_R)}Q${p(deg, RING_R + 5)} ${p(deg + 17, RING_R)}`}
    />
  );
}

const VOLTINISM_PEAKS: Record<VoltinismCode, number[]> = {
  u: [45],
  b: [0, 180],
  m: [0, 90, 180, 270],
  na: [45],
};

/**
 * Voltinism.
 *
 * What separates univoltine from multivoltine is the number of discrete adult
 * emergences inside one annual cycle, so the icon counts them: one peak, two
 * opposed, or four. Drawing it as a sine wave of N cycles would not survive —
 * two cycles and three cycles are indistinguishable on a 24-grid. Four peaks
 * rather than three for multivoltine, because ">2 generations" needs to be
 * visibly more than bivoltine's two.
 */
export function VoltinismIcon({
  variant = "na",
  ...props
}: IconProps & { variant?: VoltinismCode }) {
  return (
    <IconBase {...props} secondary={<YearRing />}>
      {VOLTINISM_PEAKS[variant].map((deg, i) => peak(deg, i, variant === "na"))}
    </IconBase>
  );
}

/**
 * Adult presence.
 *
 * A calendar rather than the year ring the other two phenology icons use, and
 * deliberately so: on the ring this was twelve radial bars and read as a sun.
 * A calendar also draws the distinction the panel needs — flight duration is a
 * measured span, this is which months are occupied, and the month cells here
 * restate the presence table rendered beside them.
 *
 * The months a species is absent are the backdrop the occupied ones are read
 * against, so they carry the supporting tone.
 */
export function AdultPresenceIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M6.2 17.4H8.4" />
          <path d="M15.6 17.4H17.8" />
        </>
      }
    >
      <rect x="3.4" y="5.2" width="17.2" height="15.4" rx="2.2" />
      <Detail>
        <path d="M3.4 9.8H20.6" />
      </Detail>
      <path d="M8 3.4V6.6" />
      <path d="M16 3.4V6.6" />
      <path d="M6.2 13.4H8.4" />
      <path d="M10.9 13.4H13.1" />
      <path d="M15.6 13.4H17.8" />
      <path d="M10.9 17.4H13.1" />
    </IconBase>
  );
}

// ---------------------------------------------------------------------------
// Life history
// ---------------------------------------------------------------------------

/**
 * A caterpillar as a row of overlapping body segments with a head capsule.
 *
 * Drawn as discrete circles rather than as one scalloped outline: the outline
 * version collapsed into an undifferentiated blob at 48px, where the repeated
 * segments read immediately as a larva.
 *
 * The overlap between segments is deliberate, but it was too deep to survive:
 * at r 2.1 on a 3.4 pitch each junction was a 0.8-wide lens, narrower than the
 * stroke crossing it, so every joint filled in and the row of circles became
 * one sausage. r 1.9 on 3.6 widens each lens to 1.4. This is re-used at
 * `scale(0.46)` inside the pupa-or-larva diapause variant, where the same
 * ratios render at under half the size, so it has the least room to spare of
 * anything in the set.
 */
function Caterpillar() {
  return (
    <>
      <circle cx="5.8" cy="16.6" r="1.9" />
      <circle cx="9.4" cy="16.6" r="1.9" />
      <circle cx="13" cy="16.6" r="1.9" />
      <circle cx="16.8" cy="15.8" r="2.3" />
      <Dot cx={17.9} cy={14.9} r={0.55} />
    </>
  );
}

/** A chrysalis, hanging by its cremaster — the silk thread is the giveaway. */
function Chrysalis({ dashed = false }: { dashed?: boolean }) {
  const dash = dashed ? DASHED : undefined;
  return (
    <>
      <path d="M12 3.6V7" style={dash} />
      <path
        style={dash}
        d="M12 7C14.8 8.4 15.6 11.4 14.6 14.4C14 16.4 13 17.8 12 18.6C11 17.8 10 16.4 9.4 14.4C8.4 11.4 9.2 8.4 12 7Z"
      />
      <Detail>
        <path d="M12 8.6C13.2 10.4 13.5 12.6 12.9 14.8" />
        <path d="M9.9 13.8H14.1" />
        <path d="M10.4 16H13.6" />
      </Detail>
    </>
  );
}

function diapauseSubject(variant: DiapauseCode): ReactNode {
  switch (variant) {
    case "l":
      return <Caterpillar />;
    case "a":
      // Drawn dorsal and small rather than in lateral profile. In profile a
      // closed-wing adult is a pointed oval, which is exactly what the
      // chrysalis is, and the two variants were impossible to tell apart.
      return (
        <>
          <path d="M12 8.2C10 6.8 7.6 6 6 6.4C5.2 8.2 5.9 10.2 7.5 11.3C9.3 11.5 10.6 11.2 12 11Z" />
          <path d="M12 8.2C14 6.8 16.4 6 18 6.4C18.8 8.2 18.1 10.2 16.5 11.3C14.7 11.5 13.4 11.2 12 11Z" />
          <path d="M12 12.9C10.2 13.3 8.4 13.8 7.5 14.8C7.1 16.1 8.2 17.4 9.8 17.6C11 16.8 11.6 15.6 12 14.3Z" />
          <path d="M12 12.9C13.8 13.3 15.6 13.8 16.5 14.8C16.9 16.1 15.8 17.4 14.2 17.6C13 16.8 12.4 15.6 12 14.3Z" />
          <path d="M12 7.6V17" />
          <Detail>
            <path d="M11.7 7.6C11 6.2 10.1 5.4 9.2 5" />
            <path d="M12.3 7.6C13 6.2 13.9 5.4 14.8 5" />
          </Detail>
        </>
      );
    case "pl":
      // "Either pupa or larva" — the one place a subject may legitimately drop
      // to the supporting tone, because the ambiguity is the meaning.
      return <Chrysalis />;
    case "p":
      return <Chrysalis />;
    case "na":
    default:
      // "No diapause or data unavailable". A solid chrysalis here asserted
      // pupal diapause for a record that says the opposite, or says nothing;
      // dashed is the same "not established" signal the voltinism icon uses.
      return <Chrysalis dashed />;
  }
}

/**
 * Diapause stage.
 *
 * Replaces an egg, which was simply the wrong datum — egg is not one of the
 * four coded stages. The frost mark stays identical across variants, so the
 * four read as one field rather than four unrelated drawings.
 */
export function DiapauseIcon({
  variant = "na",
  ...props
}: IconProps & { variant?: DiapauseCode }) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          {variant === "na" ? null : (
            <>
              <path d="M20.2 3.2V7" />
              <path d="M18.6 4.1L21.8 5.9" />
              <path d="M21.8 4.1L18.6 5.9" />
            </>
          )}
          {variant === "pl" ? (
            <g transform="translate(12 19.6) scale(0.46) translate(-12 -16.4)">
              <Caterpillar />
            </g>
          ) : null}
        </>
      }
    >
      {diapauseSubject(variant)}
    </IconBase>
  );
}

/** An egg: upright, ovoid, longitudinally ribbed, as a butterfly egg is. */
function egg(x: number, y: number, scale: number, key: number) {
  return (
    <g key={key}>
      <ellipse cx={x} cy={y} rx={1.45 * scale} ry={1.95 * scale} />
      <Detail>
        <path
          d={`M${x} ${(y - 1.7 * scale).toFixed(2)}V${(y + 1.7 * scale).toFixed(2)}`}
        />
      </Detail>
    </g>
  );
}

const EGG_LAYOUT: Record<OvipositionCode, [number, number, number][]> = {
  s: [[10.6, 14.4, 1.05]],
  // Five, not seven. At seven the outlines were closer together than the
  // stroke is wide and the raft fused into one blob.
  g: [
    [7.2, 14.2, 0.85],
    [11.2, 14.2, 0.85],
    [15.2, 14.2, 0.85],
    [9.2, 17.9, 0.85],
    [13.2, 17.9, 0.85],
  ],
  sc: [
    [5.6, 14.6, 0.85],
    [11.4, 18.4, 0.85],
    [17.2, 15.4, 0.85],
  ],
  na: [[10.6, 14.4, 1.05]],
};

/**
 * Oviposition style.
 *
 * A total rewrite: the glyph this replaces was a stock "no entry" sign with
 * two circles pasted over it, and depicted nothing to do with egg-laying.
 *
 * The leaf is seen from below, because that is the surface most butterflies
 * actually oviposit on, and the eggs — one, a raft, or scattered — are the
 * subject sitting on it.
 */
export function OvipositionIcon({
  variant = "na",
  ...props
}: IconProps & { variant?: OvipositionCode }) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M3 8C5.4 4.2 11 2.6 16.6 3.4C17.6 7.4 14.8 10.4 10 11C6.8 11.2 4.2 10 3 8Z" />
          <path d="M16.6 3.4L4.8 10.2" />
          <path d="M16.6 3.4L19.8 2.2" />
          {variant === "sc" ? (
            <>
              <path d="M8.2 12L6.8 13" />
              <path d="M14.4 12.4L16 13.4" />
            </>
          ) : null}
        </>
      }
    >
      {EGG_LAYOUT[variant].map(([x, y, s], i) => egg(x, y, s, i))}
    </IconBase>
  );
}

// ---------------------------------------------------------------------------
// Habitat affinities
//
// These four fields are free text rather than coded, so each is a single
// glyph. Each is drawn as a position on an axis rather than as a picture of a
// habitat: that is what the datum actually is.
// ---------------------------------------------------------------------------

/**
 * Canopy affinity.
 *
 * A closed canopy in profile, not a tree. The field codes which stratum a
 * species occupies, and one tree has no strata -- it just has a top. What the
 * glyph this replaces actually drew was a topiary on a stick: a single trunk
 * skewering three lens-shaped layers, and skewering is the word, because a
 * vertical through a 3-unit lens leaves less clearance either side than the
 * stroke is wide.
 *
 * The crowns are one continuous outline with three lobes rather than three
 * overlapping crown shapes. Two curves crossing at a shallow angle run closer
 * together than the stroke for most of their length and set solid -- the same
 * failure the caterpillar was redrawn to avoid. One outline cannot collide
 * with itself, and a closed canopy really is a single upper surface, so the
 * honest drawing is also the legible one.
 *
 * The scallops are shallow deliberately. A deep notch between two crowns is a
 * narrow V, and a narrow V at this weight is a filled wedge; these open to 2.6
 * units a little above their floor. The seams dropping from each notch are
 * what keep the mass reading as three crowns rather than one scalloped cloud,
 * and they are detail because without them this is still a canopy.
 *
 * The flat underside is the load-bearing line: it is the canopy floor, and the
 * brackets measure against it -- the upper stratum is the mass, the lower one
 * the space beneath. The understory is left empty rather than drawn, because a
 * species low in the forest is defined by being *under* the canopy rather than
 * by any particular shrub, and anything drawn down there would have to survive
 * at 24 units alongside three trunks.
 *
 * `EdgeForestIcon` gets the opposite construction so the two can never be
 * confused: there the trees are separate and a heavy vertical cuts them,
 * because the subject is the discontinuity. Here nothing is cut, the mass runs
 * unbroken across the frame, and the only straight lines that are not the
 * ground are the scale. Edge is a boundary; canopy is a band.
 */
export function CanopyIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M2.2 20.6H21" />
          <path d="M21 4H19.2V11H21" />
          <path d="M21 13.4H19.2V20.6" />
        </>
      }
    >
      <path d="M2.6 11C2.6 6.4 3.6 4.6 5.2 4.6C6.4 4.6 7 7.4 7.6 7.4C8.2 7.4 8.8 3.6 10 3.6C11.2 3.6 11.8 7.6 12.4 7.6C13 7.6 13.4 5 14.6 5C15.8 5 17 6.6 17 11Z" />
      <path d="M5.2 11V20.6" />
      <path d="M10 11V20.6" />
      <path d="M14.6 11V20.6" />
      <Detail>
        <path d="M7.6 7.6V9.6" />
        <path d="M12.4 7.8V9.8" />
      </Detail>
    </IconBase>
  );
}

/**
 * Edge affinity.
 *
 * The subject is the discontinuity, not the trees — so the boundary line is
 * the heaviest stroke in the icon. Drawn the other way round it would just
 * read "forest" and duplicate the canopy glyph.
 *
 * The two crowns used to share a wall: 0.2 apart at the baseline, and the
 * right one ran within 0.14 of the boundary for its lower third, so the whole
 * subject set as one mass welded to the line it is supposed to be standing
 * against. They now clear each other by 1.8 and the boundary by 1.0 — enough
 * that the boundary reads as something the trees stop at rather than
 * something they are fused to.
 */
export function EdgeForestIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M2.4 20.2H21.6" />
          <path d="M15.6 20.2V17" />
          <path d="M15.6 18.4L14.2 17" />
          <path d="M15.6 18.4L17 17" />
          <path d="M19.6 20.2V17.8" />
          <path d="M19.6 19L18.4 17.8" />
          <path d="M19.6 19L20.8 17.8" />
        </>
      }
    >
      <path d="M12.4 3.2V20.2" />
      <path d="M1.4 13.8C1.4 7.6 6.4 7.6 6.4 13.8Z" />
      <path d="M3.9 13.8V20.2" />
      <path d="M8.2 13C8.2 5.4 11.4 5.4 11.4 13Z" />
      <path d="M9.8 13V20.2" />
    </IconBase>
  );
}

/**
 * Moisture affinity.
 *
 * A position on a gradient, so the icon is an axis with a marker on it rather
 * than a picture of water. The line inside the droplet is a level gauge, not a
 * highlight.
 */
export function MoistureIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M4.5 20H19.5" />
          <path d="M4.5 18.7V21.3" />
          <path d="M12 18.4V21.6" />
          <path d="M19.5 18.7V21.3" />
        </>
      }
    >
      <path d="M12 3.2C12 3.2 7.2 8.6 7.2 11.6A4.8 4.8 0 0 0 16.8 11.6C16.8 8.6 12 3.2 12 3.2Z" />
      <Detail>
        <path d="M8 12.6C9.4 11.8 10.6 13.2 12 12.6C13.4 12 14.6 13.4 16 12.6" />
      </Detail>
    </IconBase>
  );
}

/**
 * Disturbance affinity.
 *
 * The field is about early-successional habitat, so the regrowth is the
 * payload — a stump alone would read as felling, not as the habitat a species
 * prefers. The growth rings on the cut face are what make it forestry rather
 * than clip-art.
 */
export function DisturbanceIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M2.4 20.2H21.6" />
          <path d="M3.2 20.2V17.8" />
          <path d="M20.8 20.2V18.2" />
        </>
      }
    >
      <path d="M6 20.2V11.4" />
      <path d="M12.4 20.2V11.4" />
      <ellipse cx="9.2" cy="11.4" rx="3.2" ry="1.4" />
      <Detail>
        <ellipse cx="9.2" cy="11.4" rx="1.3" ry="0.55" />
      </Detail>
      <path d="M12.4 18.6C15 18.2 16.6 16.2 16.8 13.8" />
      <path d="M16.8 13.8C14.9 13.4 14 14.6 15.2 15.8C16.3 15.6 16.8 14.7 16.8 13.8Z" />
      <path d="M16.8 13.8C18.7 13.5 19.4 14.9 18.2 15.9C17.3 15.7 16.8 14.7 16.8 13.8Z" />
    </IconBase>
  );
}

// ---------------------------------------------------------------------------
// Host plants
// ---------------------------------------------------------------------------

/**
 * One host plant family.
 *
 * The notch on the margin is a larval feeding scar — it is what makes this a
 * *host* plant rather than a leaf.
 */
export function HostPlantFamilyIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M5.4 18.6L2.8 21" />
          <path d="M12.4 17.8A1.7 1.7 0 0 0 15.2 16.2" />
        </>
      }
    >
      <path d="M5.4 18.6C5 12.6 8.6 6.6 18.6 5.4C17.8 15 12 18.8 5.4 18.6Z" />
      <path d="M5.4 18.6L18.6 5.4" />
      {/* Alternate, not opposite, and a third of the outline's weight. Paired
          veins at full weight branched from the same point on both sides,
          which drew an X at every one and turned the blade into a net. */}
      <Detail>
        <path d="M8.3 15.7Q7 15 6.6 14" />
        <path d="M11.34 12.66Q10.1 11.9 9.64 10.96" />
        <path d="M14.38 9.62Q13.1 8.9 12.68 7.92" />
        <path d="M9.62 14.38Q10.9 15.2 11.32 16.08" />
        <path d="M12.66 11.34Q13.9 12.2 14.36 13.04" />
        <path d="M15.7 8.3Q17 9.1 17.4 10" />
      </Detail>
    </IconBase>
  );
}

/**
 * A count of host plant families.
 *
 * Three leaves of visibly different architecture — simple ovate, palmately
 * lobed, linear — because different families means different leaf forms.
 * Three identical leaves would say "three plants", which is a different field.
 *
 * The two outer leaves carry no midrib. They are narrow lanceolate blades, so
 * a rib down the chord ran within a stroke of both margins for most of its
 * length and turned each leaf into a solid sliver — and a midrib is exactly
 * the kind of line the Detail rule says to cut: a leaf without one is still a
 * leaf. What distinguishes the three here is their outlines, which is the
 * whole point of the glyph.
 */
export function HostPlantFamiliesIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M12 21L11.2 17.4" />
          <path d="M12 21V18" />
          <path d="M12 21L12.8 17.8" />
        </>
      }
    >
      <path d="M11.2 17.4C7.6 16 4 13.2 3.8 7.6C6.4 10 10.2 12.6 11.2 17.4Z" />
      <path d="M12.8 17.8C15.4 15.2 18.6 11.4 19.8 6.6C17.6 9.6 14.4 13.4 12.8 17.8Z" />
      <path d="M12 18V12.6" />
      <path d="M12 12.6C10.4 12.2 9.2 11 9.4 9.4C10.2 9.6 10.8 10 11.2 10.6C10.4 8.4 10.8 5.8 12 3.8C13.2 5.8 13.6 8.4 12.8 10.6C13.2 10 13.8 9.6 14.6 9.4C14.8 11 13.6 12.2 12 12.6Z" />
    </IconBase>
  );
}

/**
 * A count of host plant accounts.
 *
 * Record cards, not plants. The field counts published accounts of host plant
 * use; the glyph this replaces showed a clump of vegetation, so a reader saw
 * "12 plants" where the data said "12 records".
 */
export function HostPlantAccountsIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <rect x="7" y="4.6" width="13.4" height="11" rx="1.6" />
          <path d="M2.6 8.2C4 6.8 5.6 6.2 7 6.2" />
          <path d="M4.6 7.2C4.2 5.7 5 4.6 6.3 4.8C6.4 6.2 5.7 7.1 4.6 7.2Z" />
        </>
      }
    >
      <rect x="3.6" y="8.4" width="13.4" height="11" rx="1.6" />
      <Detail>
        <path d="M6.4 12.2H14.2" />
        <path d="M6.4 14.6H14.2" />
        <path d="M6.4 17H11.4" />
      </Detail>
    </IconBase>
  );
}

// ---------------------------------------------------------------------------
// Specimens
// ---------------------------------------------------------------------------

/**
 * A count of specimen images.
 *
 * Not a traits field, but the last stock silhouette left in the app and it
 * would have looked wrong beside the redrawn set.
 */
export function SpecimenIcon(props: IconProps) {
  return (
    <IconBase
      {...props}
      secondary={
        <>
          <path d="M6.6 5.4H18.8A1.8 1.8 0 0 1 20.6 7.2V17" />
          <path d="M4.2 17.4L7.6 14.2" />
        </>
      }
    >
      <rect x="3.4" y="7.6" width="14" height="12" rx="1.8" />
      <Detail>
        <path d="M10.4 11.2V16.4" />
        <path d="M10.4 12.4C9 10.9 7 10.7 6.2 11.9C6 13.7 7.6 15.1 10.4 14.9Z" />
        <path d="M10.4 12.4C11.8 10.9 13.8 10.7 14.6 11.9C14.8 13.7 13.2 15.1 10.4 14.9Z" />
      </Detail>
    </IconBase>
  );
}
