"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, type CSSProperties } from "react";

import NoImage from "@/components/NoImage";

export interface SpecimenCellProps {
  /** Null for a cell with nothing to link to yet. */
  href: string | null;
  imageUrl: string | null;
  /** The binomial, already cleaned for display. */
  label: string;
  /** Printed under the name like a drawer label, in capitals. */
  family?: string | null;
  alt: string;
  /** Position in the tray; staggers the settle animation. */
  index?: number;
  /** Plays the settle-in animation when the image first arrives. */
  settle?: boolean;
  /** How wide the cell renders, for the image `sizes` hint. */
  sizes?: string;
}

/**
 * One compartment of a specimen tray: the specimen on the bare cell, and a
 * mono label under a dashed rule, the way a unit tray in a museum drawer is
 * labelled.
 *
 * The cell is its full size in every state and only the image fades in, so a
 * tray of these can stream in, or swap its specimens, without moving. A tray
 * is drawn by its parent as a grid with a one-pixel gap over the rule colour,
 * which is what draws the lines between compartments.
 */
export default function SpecimenCell({
  href,
  imageUrl,
  label,
  family,
  alt,
  index = 0,
  settle = false,
  sizes = "(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 18vw",
}: SpecimenCellProps) {
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null);
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const ready = imageUrl !== null && loadedUrl === imageUrl;
  const failed = imageUrl !== null && failedUrl === imageUrl;

  const body = (
    <>
      <div className="relative min-h-0 w-full flex-1">
        {imageUrl && !failed ? (
          <Image
            src={imageUrl}
            alt={alt}
            fill
            sizes={sizes}
            className={`object-contain drop-shadow-[0_12px_14px_rgba(56,46,46,0.2)] transition-[opacity,transform] duration-500 ease-out group-hover:-translate-y-1 group-hover:scale-105 dark:drop-shadow-[0_12px_16px_rgba(0,0,0,0.55)] ${
              ready ? `opacity-100 ${settle ? "bc-settle" : ""}` : "opacity-0"
            }`}
            style={{ "--bc-i": index } as CSSProperties}
            onLoad={() => setLoadedUrl(imageUrl)}
            onError={() => {
              setLoadedUrl(imageUrl);
              setFailedUrl(imageUrl);
            }}
            unoptimized
          />
        ) : null}
        {failed ? <NoImage /> : null}
      </div>
      <span className="mt-2 block min-h-9 border-t border-dashed border-deep-mocha-200 pt-1.5 text-left dark:border-deep-mocha-700">
        <span className="block truncate text-xs italic text-deep-mocha-700 dark:text-deep-mocha-200">
          {label || " "}
        </span>
        {family ? (
          <span className="block truncate font-label text-[10px] uppercase tracking-wider text-deep-mocha-500 dark:text-deep-mocha-400">
            {family}
          </span>
        ) : null}
      </span>
    </>
  );

  const cell =
    "group flex aspect-[1/0.9] w-full min-w-0 flex-col bg-white p-3 transition-colors dark:bg-deep-mocha-900";

  if (!href) {
    return <div className={cell}>{body}</div>;
  }
  return (
    <Link
      href={href}
      className={`${cell} hover:bg-deep-mocha-50 focus-visible:relative focus-visible:z-10 dark:hover:bg-deep-mocha-800`}
      title={label}
    >
      {body}
    </Link>
  );
}
