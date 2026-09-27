"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import NoImage from "@/components/NoImage";
import type { FeaturedSpeciesItem } from "@/lib/featuredSpecies";
import { imageUrlById } from "@/lib/images";
import { speciesUrlFromName, toBinomialName } from "@/lib/names";

/** Cards per click of an arrow. */
const STEP_CARDS = 2;

/** Placeholder cards while the sample streams in, or when it failed. */
const PLACEHOLDER_CARDS = 6;

function PlaceholderCard() {
  return (
    <div className="flex flex-col gap-2.5" aria-hidden="true">
      <div className="aspect-square rounded-2xl bg-white/50 dark:bg-deep-mocha-800/50" />
      <div className="h-5 w-3/4 rounded bg-deep-mocha-200/60 dark:bg-deep-mocha-700/60" />
      <div className="-mt-1 h-3 w-1/3 rounded bg-deep-mocha-200/40 dark:bg-deep-mocha-700/40" />
    </div>
  );
}

function FeaturedCard({ item }: { item: FeaturedSpeciesItem }) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const name = toBinomialName(item.species);
  return (
    <Link
      href={`/species/${speciesUrlFromName(item.slug)}`}
      className="group flex snap-start flex-col gap-2.5 rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-pacific-blue-500"
    >
      <div className="relative aspect-square overflow-hidden rounded-2xl bg-white shadow-sm transition-[box-shadow,transform] duration-300 ease-out group-hover:-translate-y-1 group-hover:shadow-md dark:bg-deep-mocha-800">
        {state !== "failed" ? (
          <Image
            src={imageUrlById(item.imgId)}
            alt={`Specimen of ${name}`}
            fill
            sizes="(max-width: 640px) 70vw, (max-width: 1024px) 34vw, 22vw"
            className={`object-contain p-5 drop-shadow-[0_12px_14px_rgba(56,46,46,0.2)] transition-[opacity,transform] duration-500 ease-out group-hover:scale-105 dark:drop-shadow-[0_12px_16px_rgba(0,0,0,0.55)] ${
              state === "ready" ? "opacity-100" : "opacity-0"
            }`}
            onLoad={() => setState("ready")}
            onError={() => setState("failed")}
            unoptimized
          />
        ) : (
          <NoImage />
        )}
      </div>
      <div className="flex items-baseline justify-between gap-3 px-1">
        <span className="truncate text-sm italic text-deep-mocha-900 dark:text-deep-mocha-100">
          {name}
        </span>
        <span className="shrink-0 font-label text-[11px] tabular-nums text-deep-mocha-500 dark:text-deep-mocha-400">
          {item.imageCount.toLocaleString("en-US")} images
        </span>
      </div>
      {item.family ? (
        <span className="-mt-2 px-1 font-label text-[10px] uppercase tracking-wider text-deep-mocha-500 dark:text-deep-mocha-400">
          {item.family}
        </span>
      ) : null}
    </Link>
  );
}

/**
 * The featured species as a horizontal rail: swipe or scroll on a phone,
 * arrows on a desktop, with a thumb that shows how far along the rail is.
 *
 * The rail breaks out of the page gutter to the screen edge, and its scroll
 * padding puts the first card back on the gutter, so cards scroll off the
 * edge of the screen rather than vanishing at the column edge.
 */
export default function FeaturedRail({
  species,
  pending = false,
  labelledBy,
}: {
  /** Null while pending, or when the sample could not be fetched. */
  species: FeaturedSpeciesItem[] | null;
  pending?: boolean;
  labelledBy?: string;
}) {
  const railRef = useRef<HTMLUListElement>(null);
  const [thumb, setThumb] = useState({ width: 100, offset: 0 });
  const [edges, setEdges] = useState({ start: true, end: false });

  const measure = useCallback(() => {
    const rail = railRef.current;
    if (!rail) return;
    const max = rail.scrollWidth - rail.clientWidth;
    const visible =
      rail.scrollWidth > 0 ? rail.clientWidth / rail.scrollWidth : 1;
    const progress = max > 0 ? rail.scrollLeft / max : 0;
    setThumb({ width: visible * 100, offset: progress * (1 - visible) * 100 });
    setEdges({ start: rail.scrollLeft <= 1, end: rail.scrollLeft >= max - 1 });
  }, []);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure, species]);

  const scrollByCards = (direction: 1 | -1) => {
    const rail = railRef.current;
    const card = rail?.querySelector("li");
    if (!rail || !card) return;
    const gap = parseFloat(getComputedStyle(rail).columnGap) || 0;
    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    rail.scrollBy({
      left: direction * STEP_CARDS * (card.getBoundingClientRect().width + gap),
      behavior: reduce ? "auto" : "smooth",
    });
  };

  const arrow =
    "flex h-10 w-10 items-center justify-center rounded-full border border-deep-mocha-300 bg-white/80 text-deep-mocha-700 transition-colors hover:border-deep-mocha-500 hover:text-deep-mocha-900 disabled:cursor-default disabled:opacity-40 disabled:hover:border-deep-mocha-300 dark:border-deep-mocha-600 dark:bg-deep-mocha-800/80 dark:text-deep-mocha-200 dark:hover:border-deep-mocha-400";

  return (
    <div>
      <div className="bc-bleed">
        <ul
          ref={railRef}
          onScroll={measure}
          aria-labelledby={labelledBy}
          className="scrollbar-hide m-0 grid list-none auto-cols-[minmax(200px,72vw)] grid-flow-col gap-5 overflow-x-auto p-0 pb-3 snap-x snap-mandatory [padding-inline:var(--bc-gutter)] [scroll-padding-inline:var(--bc-gutter)] sm:auto-cols-[minmax(220px,34vw)] lg:auto-cols-[minmax(240px,22vw)] 2xl:auto-cols-[300px]"
        >
          {species
            ? species.map((item) => (
                <li key={item.slug} className="min-w-0">
                  <FeaturedCard item={item} />
                </li>
              ))
            : Array.from({ length: PLACEHOLDER_CARDS }, (_, index) => (
                <li key={`placeholder-${index}`} className="min-w-0">
                  <PlaceholderCard />
                </li>
              ))}
        </ul>
      </div>
      {/* Always one line, so the section does not move when a failure
          message replaces the rail's contents. */}
      <p className="mt-1 h-5 text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
        {!species && !pending
          ? "Featured species are temporarily unavailable."
          : " "}
      </p>
      <div className="mt-2 flex items-center gap-4">
        <div
          className="h-0.5 flex-1 overflow-hidden rounded-full bg-deep-mocha-300/60 dark:bg-deep-mocha-700"
          aria-hidden="true"
        >
          <span
            className="block h-full rounded-full bg-deep-mocha-600 transition-transform duration-150 dark:bg-deep-mocha-300"
            style={{
              width: `${thumb.width}%`,
              transform: `translateX(${thumb.width > 0 ? (thumb.offset / thumb.width) * 100 : 0}%)`,
            }}
          />
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className={arrow}
            onClick={() => scrollByCards(-1)}
            disabled={!species || edges.start}
            aria-label="Previous species"
          >
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={arrow}
            onClick={() => scrollByCards(1)}
            disabled={!species || edges.end}
            aria-label="Next species"
          >
            <ChevronRight className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
