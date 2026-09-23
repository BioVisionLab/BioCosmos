"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { ImageLoading } from "@/components/Loadings";
import NoImage from "@/components/NoImage";

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
 * A species card: the image and, beneath it, the name, both inside one
 * rounded panel.
 *
 * Shared by the featured butterflies, the visual-search results and the
 * higher-taxon strips, and laid out like the ML search result card — the
 * name sits inside the panel under a square image well, rather than hanging
 * below the panel as a loose caption — so every grid of species on the site
 * reads as the same object.
 *
 * Loaded and unloaded states are one element tree with one background and
 * one height, so nothing changes colour or grows when the image arrives.
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
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const ready = imageUrl !== null && loadedUrl === imageUrl;
  const failed = imageUrl !== null && failedUrl === imageUrl;
  // An untouched visual-search slot is a faint bed rather than a solid panel,
  // so six of them do not read as six missing images.
  const resting = !imageUrl && placeholder === "empty";

  return (
    <Link
      href={href}
      aria-disabled={imageUrl ? undefined : true}
      tabIndex={imageUrl ? undefined : -1}
      className={`group w-full min-w-0 flex flex-col items-center gap-2 rounded-2xl p-4 text-center transition-[background-color,box-shadow] ${
        resting
          ? "bg-deep-mocha-200/40 dark:bg-deep-mocha-700/30"
          : "bg-deep-mocha-200 dark:bg-deep-mocha-700 shadow-sm hover:shadow-md"
      } ${imageUrl ? "" : "pointer-events-none"}`}
    >
      <div className="relative w-full aspect-square">
        {imageUrl && !failed ? (
          <Image
            src={imageUrl}
            alt={alt}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 17vw"
            className={`object-contain transition-opacity duration-200 ${
              ready ? "opacity-100" : "opacity-0"
            }`}
            onLoad={() => setLoadedUrl(imageUrl)}
            // A failed thumbnail resolves the slot too: otherwise the
            // spinner would run forever.
            onError={() => {
              setLoadedUrl(imageUrl);
              setFailedUrl(imageUrl);
            }}
            unoptimized
          />
        ) : null}
        {failed ? <NoImage /> : null}
        {!ready && placeholder === "spinner" ? (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <ImageLoading size={PLACEHOLDER_SIZE} />
          </div>
        ) : null}
      </div>
      {/* A caption, not a heading: a grid of these used to emit one <h2> per
          thumbnail. The slot is always two lines tall, even when empty, so a
          long binomial can wrap without a row of cards changing height and a
          caption that appears late is not a jump. */}
      <div className="flex min-h-10 w-full items-center justify-center">
        <p
          className="line-clamp-2 break-words text-sm leading-5 italic text-deep-mocha-800 dark:text-deep-mocha-100"
          title={label || undefined}
        >
          {label}
        </p>
      </div>
    </Link>
  );
}

export default SpeciesTile;
