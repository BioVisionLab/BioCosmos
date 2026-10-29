"use client";

import { useState } from "react";

import type { InstitutionShare } from "@/lib/higherTaxa";

/** Named holders drawn as slices of their own; the rest fold into "Others". */
const TOP_HOLDERS = 5;

/** The bucket for images with no holder on record; not a provider. */
const UNKNOWN_INSTITUTION = "Unknown";

/*
The site's chart palette (the family pies on /collections), in an order that
keeps neighbouring slices apart in hue. "Others" and "Unknown" are grays, so
they read as remainders rather than as two more institutions.
*/
const SLICE_COLORS = ["#3eadc1", "#d95326", "#62ad52", "#006666", "#e8987d"];
const OTHERS_COLOR = "#8b7474";
const UNKNOWN_COLOR = "#c9bebe";

const SIZE = 200;
const RADIUS = SIZE / 2;
const INNER_RADIUS = RADIUS * 0.62;

interface Slice {
  key: string;
  label: string;
  /** The code beside a resolved name, or what "Others" is made of. */
  detail: string | null;
  homepage: string | null;
  value: number;
  color: string;
  /** The holders folded into "Others"; empty for every other slice. */
  members: InstitutionShare[];
}

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** As the header formats a share: a decimal only where it says something. */
function formatShare(value: number, total: number): string {
  const share = (value / total) * 100;

  if (share > 0 && share < 0.1) return "<0.1%";

  if (share < 10) return `${share.toFixed(1)}%`;

  return `${Math.round(share)}%`;
}

function buildSlices(institutions: InstitutionShare[]): Slice[] {
  const named = institutions
    .filter((share) => share.code !== UNKNOWN_INSTITUTION)
    .sort((a, b) => b.imageCount - a.imageCount);
  const unknown = institutions
    .filter((share) => share.code === UNKNOWN_INSTITUTION)
    .reduce((total, share) => total + share.imageCount, 0);
  const rest = named.slice(TOP_HOLDERS);

  const slices: Slice[] = named.slice(0, TOP_HOLDERS).map((share, index) => ({
    key: share.code,
    label: share.name ?? share.code,
    detail: codeBesideName(share),
    homepage: share.homepage,
    value: share.imageCount,
    color: SLICE_COLORS[index],
    members: [],
  }));

  if (rest.length > 0) {
    slices.push({
      key: "others",
      label: "Others",
      detail: `${rest.length} more ${rest.length === 1 ? "institution" : "institutions"}`,
      homepage: null,
      value: rest.reduce((total, share) => total + share.imageCount, 0),
      color: OTHERS_COLOR,
      members: rest,
    });
  }

  // Not a holder, so never one of the five and never folded into "Others",
  // but drawn, so the slices still account for every image.
  if (unknown > 0) {
    slices.push({
      key: UNKNOWN_INSTITUTION,
      label: "Holder not recorded",
      detail: null,
      homepage: null,
      value: unknown,
      color: UNKNOWN_COLOR,
      members: [],
    });
  }

  return slices;
}

/**
 * A point on the ring, to two decimals: the server and the browser disagree
 * in the last digits of a cosine, which React reports as a hydration
 * mismatch on every slice.
 */
function point(radius: number, angle: number): string {
  const x = (RADIUS + radius * Math.cos(angle)).toFixed(2);
  const y = (RADIUS + radius * Math.sin(angle)).toFixed(2);

  return `${x} ${y}`;
}

/** The code beside a resolved name, unless the code is the name itself. */
function codeBesideName(share: InstitutionShare): string | null {
  return share.name && share.name !== share.code ? share.code : null;
}

/** One ring segment from `start` to `end`, in radians clockwise from 12. */
function arcPath(start: number, end: number): string {
  // A lone slice is a full ring, which a single arc cannot draw: its start
  // and end points coincide. Two half-ring segments can.
  if (end - start >= 2 * Math.PI - 1e-6) {
    const middle = start + Math.PI;

    return `${arcPath(start, middle)} ${arcPath(middle, start + 2 * Math.PI)}`;
  }

  const large = end - start > Math.PI ? 1 : 0;

  return [
    `M ${point(RADIUS, start)}`,
    `A ${RADIUS} ${RADIUS} 0 ${large} 1 ${point(RADIUS, end)}`,
    `L ${point(INNER_RADIUS, end)}`,
    `A ${INNER_RADIUS} ${INNER_RADIUS} 0 ${large} 0 ${point(INNER_RADIUS, start)}`,
    "Z",
  ].join(" ");
}

/** Each slice's segment, laid end to end clockwise from 12 o'clock. */
function ringArcs(slices: Slice[], total: number): string[] {
  const arcs: string[] = [];
  let angle = -Math.PI / 2;

  for (const slice of slices) {
    const start = angle;
    angle += (slice.value / total) * 2 * Math.PI;
    arcs.push(arcPath(start, angle));
  }

  return arcs;
}

/**
 * Images of a taxon by the institution that holds the specimen.
 *
 * Hovering or focusing a slice or a legend row highlights both and puts that
 * holder's share in the middle of the ring. The legend carries every number
 * the chart does, so the chart itself is decorative to a screen reader.
 */
export default function InstitutionDonut({
  institutions,
}: {
  institutions: InstitutionShare[];
}) {
  const [active, setActive] = useState<number | null>(null);
  const slices = buildSlices(institutions);
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  if (total === 0) {
    return (
      <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        No holding institution is on record for these images.
      </p>
    );
  }

  const holders = institutions.filter(
    (share) => share.code !== UNKNOWN_INSTITUTION,
  ).length;
  const arcs = ringArcs(slices, total);
  const selected = active === null ? null : slices[active];

  return (
    <div className="flex flex-wrap items-center gap-x-10 gap-y-6">
      <svg
        viewBox={`-8 -8 ${SIZE + 16} ${SIZE + 16}`}
        className="mx-auto h-52 w-52 shrink-0 sm:mx-0"
        aria-hidden="true"
      >
        {slices.map((slice, index) => (
          <path
            key={slice.key}
            d={arcs[index]}
            fill={slice.color}
            onMouseEnter={() => setActive(index)}
            onMouseLeave={() => setActive(null)}
            className="cursor-pointer stroke-white transition-[opacity,transform] duration-150 dark:stroke-deep-mocha-900"
            strokeWidth={2}
            style={{
              opacity: active === null || active === index ? 1 : 0.4,
              transform: active === index ? "scale(1.04)" : undefined,
              transformOrigin: `${RADIUS}px ${RADIUS}px`,
            }}
          />
        ))}
        <text
          x={RADIUS}
          y={RADIUS - 2}
          textAnchor="middle"
          className="fill-current text-[26px] font-semibold"
        >
          {selected ? formatShare(selected.value, total) : formatCount(total)}
        </text>
        <text
          x={RADIUS}
          y={RADIUS + 20}
          textAnchor="middle"
          className="fill-deep-mocha-600 text-[13px] dark:fill-deep-mocha-400"
        >
          {selected
            ? selected.detail && selected.key !== "others"
              ? selected.detail
              : selected.label
            : "images"}
        </text>
      </svg>

      <div className="min-w-64 flex-1">
        <ul className="space-y-0.5" aria-label="Images by holding institution">
          {slices.map((slice, index) => (
            <li
              key={slice.key}
              tabIndex={0}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
              className={`rounded-lg px-2 py-1.5 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-pacific-blue-500 ${
                active === index
                  ? "bg-deep-mocha-200/60 dark:bg-deep-mocha-700/60"
                  : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className="h-3 w-3 shrink-0 rounded-sm"
                  style={{ backgroundColor: slice.color }}
                />
                <span className="min-w-0 flex-1">
                  {slice.homepage ? (
                    <a
                      href={slice.homepage}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {slice.label}
                    </a>
                  ) : (
                    slice.label
                  )}
                  {slice.detail ? (
                    <span className="ml-1.5 text-deep-mocha-500 dark:text-deep-mocha-400">
                      {slice.detail}
                    </span>
                  ) : null}
                </span>
                <span className="tabular-nums text-deep-mocha-700 dark:text-deep-mocha-300">
                  {formatCount(slice.value)}
                </span>
                <span className="w-12 text-right tabular-nums text-deep-mocha-500 dark:text-deep-mocha-400">
                  {formatShare(slice.value, total)}
                </span>
              </div>
              {slice.members.length > 0 ? (
                <details className="ml-6 mt-1">
                  <summary className="cursor-pointer text-xs text-pacific-blue-700 dark:text-pacific-blue-400">
                    Show all
                  </summary>
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {slice.members.map((member) => (
                      <li key={member.code} className="flex gap-3">
                        <span className="min-w-0 flex-1">
                          {member.name ?? member.code}
                          {codeBesideName(member) ? (
                            <span className="ml-1.5 text-deep-mocha-500 dark:text-deep-mocha-400">
                              {member.code}
                            </span>
                          ) : null}
                        </span>
                        <span className="tabular-nums text-deep-mocha-600 dark:text-deep-mocha-400">
                          {formatCount(member.imageCount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
