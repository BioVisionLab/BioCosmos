"use client";

import { useEffect, useState } from "react";

import MorphospacePlot from "@/components/morphospace/MorphospacePlot";
import { MorphospaceIntro } from "@/components/morphospace/MorphospaceSection";
import {
  SIDES,
  fetchScopeMorphospace,
  fetchSpeciesMorphospace,
  formatPercent,
  type ScopeMorphospace,
  type SpeciesMorphospace as SpeciesPayload,
} from "@/lib/morphospace";
import { familyHref, genusHref } from "@/lib/taxonSlug";
import { useInView } from "@/lib/useInView";

type Level = "genus" | "family";

function rankText(
  value: number | null | undefined,
  scope: string | null | undefined,
) {
  if (value == null || !scope) return undefined;
  return `higher than ${formatPercent(value)} of ${scope}`;
}

/**
 * Where a species sits in its genus's (or family's) dorso-ventral morphospace,
 * and how variable it is compared with its relatives.
 */
export default function SpeciesMorphospace({ species }: { species: string }) {
  const { ref, inView: near } = useInView<HTMLDivElement>("400px");
  const [info, setInfo] = useState<SpeciesPayload | null | undefined>(
    undefined,
  );
  // Null until the reader picks; the default follows what is available.
  const [picked, setPicked] = useState<Level | null>(null);
  // Scopes by "rank/key", so switching back and forth fetches each once.
  const [scopes, setScopes] = useState<Record<string, ScopeMorphospace | null>>(
    {},
  );

  useEffect(() => {
    if (!near || !species) return;
    let cancelled = false;
    fetchSpeciesMorphospace(species)
      .then((result) => {
        if (cancelled) return;
        setInfo(result);
      })
      .catch(() => !cancelled && setInfo(null));
    return () => {
      cancelled = true;
    };
  }, [near, species]);

  // A genus of one or two species has no space of its own.
  const level: Level =
    picked ?? (info && !info.genus?.available ? "family" : "genus");
  const target = info ? info[level] : null;
  const scopeKey = target?.available ? `${level}/${target.key}` : null;

  useEffect(() => {
    if (!scopeKey || scopeKey in scopes) return;
    const [rank, key] = scopeKey.split("/") as [Level, string];
    let cancelled = false;
    const store = (result: ScopeMorphospace | null) => {
      if (!cancelled)
        setScopes((previous) => ({ ...previous, [scopeKey]: result }));
    };
    fetchScopeMorphospace(rank, key)
      .then(store)
      .catch(() => store(null));
    return () => {
      cancelled = true;
    };
  }, [scopeKey, scopes]);

  const scope: ScopeMorphospace | null | undefined =
    info === undefined ? undefined : scopeKey ? scopes[scopeKey] : null;

  if (info === null) return <div ref={ref} />;

  const genusName = info?.genus?.name;
  const familyName = info?.family?.name;

  return (
    <div
      ref={ref}
      className="p-4 border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl max-w-full bg-white dark:bg-deep-mocha-950"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <h3 className="text-lg font-medium">Morphospace</h3>
        {info && (
          <div
            role="radiogroup"
            aria-label="Compare within"
            className="inline-flex rounded-md border border-deep-mocha-200 dark:border-deep-mocha-700 overflow-hidden text-sm"
          >
            {(["genus", "family"] as const).map((l) => {
              const scopeRef = info[l];
              const disabled = !scopeRef?.available;
              return (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  aria-checked={level === l}
                  disabled={disabled}
                  onClick={() => setPicked(l)}
                  className={`px-2.5 py-1 disabled:opacity-40 ${
                    level === l
                      ? "bg-deep-mocha-700 text-white dark:bg-deep-mocha-200 dark:text-deep-mocha-950 font-medium"
                      : "hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-800"
                  }`}
                >
                  {l === "genus" ? "Within genus" : "Within family"}
                  {scopeRef?.name && (
                    <span className="italic"> {scopeRef.name}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
      <MorphospaceIntro />

      {info && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
          {SIDES.map((side) => {
            const s = info.sides[side];
            const pct = s?.percentile[level];
            return (
              <div
                key={side}
                className="rounded-lg border border-deep-mocha-100 dark:border-deep-mocha-800 p-3"
              >
                <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
                  {side === "dorsal" ? "Dorsal" : "Ventral"} variation within
                  species
                </p>
                <p className="text-lg font-semibold tabular-nums">
                  {s?.dispersion == null ? "–" : s.dispersion.toFixed(3)}
                </p>
                <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
                  {s
                    ? (rankText(
                        pct,
                        level === "genus" ? genusName : familyName,
                      ) ?? `${s.nImages.toLocaleString()} images`)
                    : "No photographs of this side"}
                </p>
              </div>
            );
          })}
          <div className="rounded-lg border border-deep-mocha-100 dark:border-deep-mocha-800 p-3">
            <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
              Dorsal–ventral difference
            </p>
            <p className="text-lg font-semibold tabular-nums">
              {info.dvDivergence == null ? "–" : info.dvDivergence.toFixed(3)}
            </p>
            <p className="text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
              {info.dvDivergence == null
                ? "Needs both sides"
                : rankText(
                    info.dvDivergencePercentile[level],
                    level === "genus" ? genusName : familyName,
                  )}
            </p>
          </div>
        </div>
      )}

      {scope === undefined ? (
        <div className="h-110 rounded-lg border border-deep-mocha-100 dark:border-deep-mocha-800 animate-pulse" />
      ) : scope === null ? (
        <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
          Too few relatives with enough photographs to draw a morphospace.
        </p>
      ) : (
        <>
          <MorphospacePlot
            key={scope.scope.key}
            data={scope}
            initialSelection={
              info
                ? [{ kind: "species", key: info.species, label: info.species }]
                : []
            }
          />
          <p className="mt-2 text-xs text-deep-mocha-600 dark:text-deep-mocha-400">
            Compared with {scope.scope.nSpecies.toLocaleString()} species of{" "}
            <a
              className="italic underline"
              href={
                level === "genus"
                  ? genusHref(scope.scope.name)
                  : familyHref(scope.scope.name)
              }
            >
              {scope.scope.name}
            </a>
            .
          </p>
        </>
      )}
    </div>
  );
}
