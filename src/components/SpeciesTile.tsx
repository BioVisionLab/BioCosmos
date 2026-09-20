"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { ImageLoading } from "@/components/Loadings";

const PLACEHOLDER_SIZE = 60;

export interface SpeciesTileProps {
  /** Where the tile links to; species pages key on the recorded slug. */
  href: string;
  /** Null while the tile has no image to show. */
  imageUrl: string | null;
  /** The name shown beneath the tile, already cleaned for display. */
  label: string;
  alt: string;
  /**
   * What an image-less tile shows. "spinner" is the default; "empty" is the
   * resting bed the visual-search grid sits on before a search has been run,
   * where six spinners would claim work that is not happening.
   */
  placeholder?: "spinner" | "empty";
}

/**
 * A square species tile: the image in a rounded panel, the name beneath it.
 *
 * Shared by the featured butterflies and the visual-search results, so the
 * two grids on the landing page are the same object rather than two cards
 * that merely started out looking alike.
 *
 * Loaded and unloaded states are one element tree with one background and
 * one height. They used to be two different trees — a bare `div` without a
 * caption, and a `Link` with one, in two different shades — so every tile
 * changed colour and grew taller the moment its image arrived.
 */
export function SpeciesTile({
  href,
  imageUrl,
  label,
  alt,
  placeholder = "spinner",
}: SpeciesTileProps) {
  // Tracked by URL rather than by a boolean: the visual-search slots swap
  // their `src` in place, and a boolean would report the outgoing image as
  // loaded while the incoming one was still on the wire.
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null);
  const ready = imageUrl !== null && loadedUrl === imageUrl;

  return (
    <Link
      href={href}
      aria-disabled={imageUrl ? undefined : true}
      tabIndex={imageUrl ? undefined : -1}
      className={`w-full flex flex-col justify-center items-center text-center group ${
        imageUrl ? "" : "pointer-events-none"
      }`}
    >
      {/* One box, one size, in every state. Only the fill changes: an
          untouched visual-search slot is a faint bed rather than a solid
          panel, so six of them do not read as six missing images. */}
      <div
        className={`relative w-full aspect-square rounded-2xl p-4 overflow-hidden transition-[background-color,box-shadow] ${
          imageUrl || placeholder === "spinner"
            ? "bg-deep-mocha-200 dark:bg-deep-mocha-700 shadow-sm group-hover:shadow-md"
            : "bg-deep-mocha-200/40 dark:bg-deep-mocha-700/30"
        }`}
      >
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={alt}
            fill
            sizes="(max-width: 768px) 50vw, (max-width: 1200px) 25vw, 16vw"
            className={`object-contain transition-opacity duration-200 ${
              ready ? "opacity-100" : "opacity-0"
            }`}
            // A failed thumbnail resolves the slot too: otherwise the
            // spinner beneath it would run forever.
            onLoad={() => setLoadedUrl(imageUrl)}
            onError={() => setLoadedUrl(imageUrl)}
            unoptimized
          />
        ) : null}
        {!ready && placeholder === "spinner" ? (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <ImageLoading size={PLACEHOLDER_SIZE} />
          </div>
        ) : null}
      </div>
      {/* A caption, not a heading: a grid of these used to emit one <h2> per
          thumbnail, which reads as a page full of top-level sections. It is
          rendered even when empty, because the line is part of the tile's
          height and a caption that appears late is a jump. */}
      <p
        className="w-full text-sm truncate italic text-center text-deep-mocha-600 dark:text-deep-mocha-400 mt-2 px-1"
        title={label || undefined}
      >
        {label || " "}
      </p>
    </Link>
  );
}

export default SpeciesTile;
