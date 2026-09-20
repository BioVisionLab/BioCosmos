"use client";

/**
 * The shared vocabulary of the two image-metadata panels — the one under the
 * species gallery and the one in the specimen modal.
 *
 * They sit in different containers (a two-column card, and a narrow column in
 * an overlay) so they do not share a layout, but everything that makes them
 * look like the same thing lives here: the label and value styling, and the
 * row of outbound links that closes both.
 */

import { SpecimenImageMeta, sourceDbHref } from "@/lib/imageMetadata";

export const METADATA_LABEL = "font-medium whitespace-nowrap";
export const METADATA_VALUE = "text-deep-mocha-700 dark:text-deep-mocha-300";
export const METADATA_LINK =
  "text-deep-mocha-700 dark:text-deep-mocha-300 underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300";
export const METADATA_EMPTY = "text-deep-mocha-400 dark:text-deep-mocha-600";

/**
 * License, source and image links, in that order.
 *
 * Last in both panels and always together: these three leave the page, so
 * they belong after everything that describes the specimen rather than
 * interleaved with it.
 */
export function MetadataLinks({
  meta,
  className = "",
}: {
  meta: SpecimenImageMeta;
  className?: string;
}) {
  const license =
    typeof meta.license === "string" && meta.license.startsWith("http")
      ? meta.license
      : null;
  const imageLink = typeof meta.uri === "string" && meta.uri ? meta.uri : null;

  return (
    <div
      className={`mt-1 pt-2 border-t border-deep-mocha-200 dark:border-deep-mocha-700 flex flex-wrap items-center gap-x-4 gap-y-1 leading-normal ${className}`}
    >
      {license ? (
        <a
          href={license}
          target="_blank"
          rel="noopener noreferrer"
          className={METADATA_LINK}
          aria-label="Open license"
        >
          License
        </a>
      ) : (
        <span className={METADATA_EMPTY}>No license</span>
      )}
      <a
        href={sourceDbHref(meta.uuid)}
        target="_blank"
        rel="noopener noreferrer"
        className={METADATA_LINK}
        aria-label="Open source database record"
      >
        Source Link
      </a>
      {imageLink ? (
        <a
          href={imageLink}
          target="_blank"
          rel="noopener noreferrer"
          className={METADATA_LINK}
          aria-label="Open image link"
        >
          Image Link
        </a>
      ) : null}
    </div>
  );
}
