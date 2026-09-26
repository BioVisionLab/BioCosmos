"use client";

import "./morphospace.css";
import { useMemo, useState } from "react";
import Link from "next/link";

import type {
  Disparity,
  ScopeMorphospace,
  SideDisparity,
} from "@/lib/morphospace";
import { formatPercent } from "@/lib/morphospace";
import { genusHref } from "@/lib/taxonSlug";

function Stat({
  label,
  value,
  note,
  children,
}: {
  label: React.ReactNode;
  value: string;
  note?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-deep-mocha-100 dark:border-deep-mocha-800 p-3">
      <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
        {label}
      </p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
      {note && (
        <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
          {note}
        </p>
      )}
      {children}
    </div>
  );
}

/**
 * How to read a Mantel r in words. The bands are the conventional ones for a
 * correlation; they describe strength, not significance, which is the p-value.
 */
export function integrationStrength(r: number): string {
  const size = Math.abs(r);
  const strength =
    size >= 0.7
      ? "Strong"
      : size >= 0.4
        ? "Moderate"
        : size >= 0.2
          ? "Weak"
          : "Little or no";
  if (size < 0.2) return "Little or no shared pattern";
  return r > 0
    ? `${strength}: the two sides vary together`
    : `${strength}: the sides vary in opposite ways`;
}

/** Where r falls on its full −1 to 1 range, with the three reference points labelled. */
function MantelScale({ r }: { r: number }) {
  const position = ((Math.max(-1, Math.min(1, r)) + 1) / 2) * 100;
  return (
    <div className="mt-2" aria-hidden>
      <div className="relative h-1.5 rounded-full bg-deep-mocha-200 dark:bg-deep-mocha-700">
        <span className="absolute left-1/2 -top-0.75 h-3 w-px bg-deep-mocha-600 dark:bg-deep-mocha-400" />
        <span
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white dark:border-deep-mocha-950"
          style={{ left: `${position}%`, background: "var(--ms-dorsal)" }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-deep-mocha-600 dark:text-deep-mocha-400">
        <span>−1 opposite</span>
        <span>0 unrelated</span>
        <span>1 identical</span>
      </div>
    </div>
  );
}

/** Dorsal vs ventral rarefied disparity as dot-and-whisker on one shared axis. */
function SideDisparityChart({ disparity }: { disparity: Disparity }) {
  const rows = (["dorsal", "ventral"] as const)
    .map((side) => [side, disparity[side]] as const)
    .filter((row): row is readonly ["dorsal" | "ventral", SideDisparity] =>
      Boolean(row[1] && row[1].rarefiedMean != null),
    );
  if (rows.length === 0) return null;
  const max =
    Math.max(...rows.map(([, d]) => d.rarefiedHigh ?? d.rarefiedMean ?? 0)) *
    1.1;
  const W = 320,
    rowH = 28,
    left = 64,
    right = 56;
  const x = (v: number) => left + (v / max) * (W - left - right);
  return (
    <figure className="morphospace-viz">
      <svg
        viewBox={`0 0 ${W} ${rows.length * rowH}`}
        className="w-full max-w-sm"
        role="img"
        aria-label="Rarefied disparity by side, with 95% interval"
      >
        {rows.map(([side, d], row) => {
          const y = row * rowH + 14;
          const color =
            side === "dorsal" ? "var(--ms-dorsal)" : "var(--ms-ventral)";
          return (
            <g key={side}>
              <text
                x={0}
                y={y}
                dominantBaseline="middle"
                className="fill-current text-[11px] capitalize"
              >
                {side}
              </text>
              <line
                x1={x(d.rarefiedLow ?? 0)}
                x2={x(d.rarefiedHigh ?? 0)}
                y1={y}
                y2={y}
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
              />
              <circle
                cx={x(d.rarefiedMean ?? 0)}
                cy={y}
                r={5}
                fill={color}
                stroke="var(--ms-surface)"
                strokeWidth={2}
              />
              <text
                x={W}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-current text-[11px] tabular-nums"
              >
                {(d.rarefiedMean ?? 0).toFixed(3)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
        Sum of variances of species centroids in the full embedding, resampled
        at {rows[0][1].rarefyK} species (mean and 95% interval) using
        rarefaction to account for different numbers of species on each side.
      </figcaption>
    </figure>
  );
}

/** A family's genera: dorsal against ventral disparity, with the 1:1 line. */
function GenusDisparityScatter({ data }: { data: ScopeMorphospace }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const genera = useMemo(
    () =>
      data.children
        .map((g) => ({
          name: g.name,
          nSpecies: g.nSpecies,
          dorsal: g.disparity.dorsal?.rarefiedMean ?? null,
          ventral: g.disparity.ventral?.rarefiedMean ?? null,
          r: g.integration.r,
        }))
        .filter(
          (g): g is typeof g & { dorsal: number; ventral: number } =>
            g.dorsal != null && g.ventral != null,
        ),
    [data.children],
  );
  if (genera.length < 3) return null;
  // One domain for both axes, fitted to the data, so the 1:1 line stays a
  // diagonal and the points are not crowded into a corner above zero.
  const values = genera.flatMap((g) => [g.dorsal, g.ventral]);
  const span = Math.max(...values) - Math.min(...values) || 1;
  const min = Math.min(...values) - span * 0.08;
  const max = Math.max(...values) + span * 0.08;
  const S = 280,
    pad = 36;
  const p = (v: number) => pad + ((v - min) / (max - min)) * (S - pad - 8);
  const flip = (v: number) => S - p(v);
  const above = genera.filter((g) => g.ventral > g.dorsal).length;
  const active = genera.find((g) => g.name === hovered);
  return (
    <figure className="morphospace-viz">
      <div className="relative inline-block">
        <svg
          viewBox={`0 0 ${S} ${S}`}
          className="w-full max-w-xs"
          role="img"
          aria-label="Genus disparity, dorsal against ventral"
        >
          <line
            x1={p(min)}
            y1={flip(min)}
            x2={p(max)}
            y2={flip(max)}
            stroke="var(--ms-link)"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
          <text
            x={pad}
            y={S - pad + 12}
            className="fill-current text-[10px] tabular-nums"
          >
            {min.toFixed(2)}
          </text>
          <text
            x={S - 8}
            y={S - pad + 12}
            textAnchor="end"
            className="fill-current text-[10px] tabular-nums"
          >
            {max.toFixed(2)}
          </text>
          <text
            x={pad - 4}
            y={S - pad}
            textAnchor="end"
            className="fill-current text-[10px] tabular-nums"
          >
            {min.toFixed(2)}
          </text>
          <text
            x={pad - 4}
            y={14}
            textAnchor="end"
            className="fill-current text-[10px] tabular-nums"
          >
            {max.toFixed(2)}
          </text>
          <line
            x1={pad}
            x2={S - 8}
            y1={S - pad}
            y2={S - pad}
            stroke="var(--ms-grid)"
          />
          <line x1={pad} x2={pad} y1={8} y2={S - pad} stroke="var(--ms-grid)" />
          <text
            x={(S + pad) / 2}
            y={S - 8}
            textAnchor="middle"
            className="fill-current text-[11px]"
          >
            Dorsal disparity
          </text>
          <text
            transform={`translate(12 ${(S - pad) / 2}) rotate(-90)`}
            textAnchor="middle"
            className="fill-current text-[11px]"
          >
            Ventral disparity
          </text>
          {genera.map((g) => (
            <Link key={g.name} href={genusHref(g.name)}>
              <circle
                cx={p(g.dorsal)}
                cy={flip(g.ventral)}
                r={hovered === g.name ? 6 : 4}
                fill="var(--ms-dorsal)"
                fillOpacity={0.75}
                stroke="var(--ms-surface)"
                strokeWidth={2}
                onMouseEnter={() => setHovered(g.name)}
                onMouseLeave={() => setHovered(null)}
              >
                <title>{`${g.name}: ${g.nSpecies} species`}</title>
              </circle>
            </Link>
          ))}
        </svg>
        {active && (
          <div className="pointer-events-none absolute top-1 right-1 rounded-md border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white dark:bg-deep-mocha-950 px-2 py-1 text-xs shadow">
            <p className="italic font-semibold">{active.name}</p>
            <p className="tabular-nums text-deep-mocha-600 dark:text-deep-mocha-400">
              {active.nSpecies} species · D {active.dorsal.toFixed(3)} · V{" "}
              {active.ventral.toFixed(3)}
              {active.r != null &&
                ` · integration r ${active.r.toFixed(2)} (−1 to 1)`}
            </p>
          </div>
        )}
      </div>
      <figcaption className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400 max-w-xs">
        {above} of {genera.length} genera lie above the dashed line indicates
        greater disparity on the ventral side than on the dorsal side, and vice
        versa. Each point represent a genus with ≥3 species.
      </figcaption>
    </figure>
  );
}

export default function DisparityPanel({ data }: { data: ScopeMorphospace }) {
  const { scope } = data;
  const { r, p, n } = scope.integration;
  const pc12 = scope.explained[0] + scope.explained[1];
  return (
    <div className="morphospace-viz grid gap-4 lg:grid-cols-[1fr_auto] rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white dark:bg-deep-mocha-950 p-4">
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Stat
            label="Species"
            value={scope.nSpecies.toLocaleString()}
            note={`${scope.nSpeciesBoth.toLocaleString()} seen from both sides`}
          />
          <Stat
            label="PC1 + PC2"
            value={formatPercent(pc12, 1)}
            note="of centroid variance"
          />
          <Stat
            label={
              <>
                Dorso-ventral integration
                <span className="block">Mantel r, ranges −1 to 1</span>
              </>
            }
            value={r == null ? "–" : `r = ${r.toFixed(2)}`}
            note={
              r == null
                ? "needs ≥5 species with both sides"
                : // Non-breaking spaces keep "310 species" and "p ≤ 0.001" whole.
                  `${integrationStrength(r)} · ${n}\u00a0species · ${
                    p == null
                      ? "p not computed for this many species"
                      : `p\u00a0${p <= 0.001 ? "≤\u00a00.001" : `=\u00a0${p.toFixed(3)}`}`
                  }`
            }
          >
            {r != null && <MantelScale r={r} />}
          </Stat>
          <Stat
            label="Axes fitted on"
            value={
              scope.basis === "both_sides" ? "Both sides" : "All centroids"
            }
            note="shared by dorsal and ventral"
          />
        </div>
        <SideDisparityChart disparity={data.disparity} />
        <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400 max-w-prose">
          Morphological integration is the Mantel correlation between pairwise
          differences in dorsal and ventral coloration, ranging from −1 to 1.
          Values near 1 indicate similar patterns of variation across both
          surfaces; values near 0 indicate largely independent variation;
          negative values indicate opposing patterns. As a rough guide, |r|
          below 0.2 is little or no integration, 0.2–0.4 weak, 0.4–0.7 moderate,
          and ≥0.7 strong. The permutation p-value tests whether the observed
          correlation is greater than expected by chance.
        </p>
      </div>
      {scope.rank === "family" && <GenusDisparityScatter data={data} />}
    </div>
  );
}
