"use client";

import Image from "next/image";
import Link from "next/link";

import { ImageLoading } from "@/components/Loadings";

const PLACEHOLDER_SIZE = 60;

export interface SpeciesTileProps {
  /** Where the tile links to; species pages key on the recorded slug. */
  href: string;
  /** Null while the thumbnail is still being fetched. */
  imageUrl: string | null;
  /** The name shown beneath the tile, already cleaned for display. */
  label: string;
  alt: string;
}

/**
 * A square species tile: the image in a rounded panel, the name beneath it.
 *
 * Shared by the featured butterflies and the visual-search results, so the
 * two grids on the landing page are the same object rather than two cards
 * that merely started out looking alike.
 */
export function SpeciesTile({ href, imageUrl, label, alt }: SpeciesTileProps) {
  if (!imageUrl) {
    return (
      <div className="w-full aspect-square flex flex-col items-center justify-center bg-deep-mocha-100 dark:bg-deep-mocha-800 rounded-2xl">
        <ImageLoading size={PLACEHOLDER_SIZE} />
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="w-full flex flex-col justify-center items-center text-center group"
    >
      <div className="relative w-full aspect-square bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 overflow-hidden shadow-sm group-hover:shadow-md transition-shadow">
        <Image
          src={imageUrl}
          alt={alt}
          fill
          className="object-contain p-4"
          sizes="(max-width: 768px) 50vw, (max-width: 1200px) 25vw, 16vw"
          unoptimized
        />
      </div>
      {/* A caption, not a heading: a grid of these used to emit one <h2> per
          thumbnail, which reads as a page full of top-level sections. */}
      <p
        className="w-full text-sm truncate italic text-center text-deep-mocha-400 mt-2 px-1"
        title={label}
      >
        {label}
      </p>
    </Link>
  );
}

export default SpeciesTile;
