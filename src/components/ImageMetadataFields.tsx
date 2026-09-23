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

import Link from "next/link";
import { HelpCircle } from "lucide-react";

import {
  SpecimenImageMeta,
  SpecimenProvenance,
  sourceDbHref,
} from "@/lib/imageMetadata";

export const METADATA_LABEL = "font-medium whitespace-nowrap";
export const METADATA_VALUE = "text-deep-mocha-700 dark:text-deep-mocha-300";
export const METADATA_LINK =
  "text-deep-mocha-700 dark:text-deep-mocha-300 underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300";
export const METADATA_EMPTY = "text-deep-mocha-400 dark:text-deep-mocha-600";

/**
 * A link to the page that explains a whole matching vocabulary.
 *
 * Each badge already explains its own code on hover. This is the other
 * question — what the check is and how it reached that verdict — which a
 * tooltip is the wrong size for. One per block, never one per badge: these
 * panels are dense enough already.
 */
export function MatchingHelpLink({
  section,
  label,
}: {
  section: "taxonomy-matching" | "coordinate-matching";
  label: string;
}) {
  return (
    <Link
      href={`/resources#${section}`}
      aria-label={label}
      title={label}
      className="inline-flex items-center text-deep-mocha-400 transition-colors hover:text-pacific-blue-700 dark:text-deep-mocha-500 dark:hover:text-pacific-blue-300"
    >
      <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
    </Link>
  );
}

/**
 * The specimen's catalog number.
 *
 * The holding institution used to sit here beside it, and has moved down to
 * the footer to sit with the source database: those two are both answers to
 * "where did this record come from", and reading them together is what makes
 * either of them useful. The catalog number is a property of the specimen,
 * not of its provenance trail, so it stays up here with the rest of the
 * record.
 *
 * Omitted entirely when nothing was recorded, the same contract as the
 * taxonomy and locality blocks: no run, no empty row.
 */
export function ProvenanceBlock({
  provenance,
}: {
  provenance: SpecimenProvenance | null;
}) {
  if (!provenance?.catalogNumber) return null;
  return (
    <div className="col-span-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 min-w-0 leading-normal">
      <span className="flex items-baseline gap-1 min-w-0">
        <span className={METADATA_LABEL}>Specimen ID:</span>
        <span className={`truncate ${METADATA_VALUE}`}>
          {provenance.catalogNumber}
        </span>
      </span>
    </div>
  );
}

/**
 * The holding institution: its full name, linked to its website when public
 * records give one, with the recorded code beside it.
 *
 * The code stays visible because it is what the record says and what a
 * citation uses; the name only explains it. A long name truncates and keeps
 * the full text in its tooltip, while the code never shrinks. A code that
 * could not be resolved is shown on its own, as before.
 */
function SpecimenHolder({ provenance }: { provenance: SpecimenProvenance }) {
  const { institutionCode: code, institutionName: name } = provenance;
  const homepage = provenance.institutionHomepage;
  if (!name) {
    return <span className={`truncate ${METADATA_VALUE}`}>{code}</span>;
  }
  return (
    <span className="flex items-baseline gap-1 min-w-0">
      {homepage ? (
        <a
          href={homepage}
          target="_blank"
          rel="noopener noreferrer"
          title={name}
          className={`truncate ${METADATA_LINK}`}
          aria-label={`${name} website`}
        >
          {name}
        </a>
      ) : (
        <span title={name} className={`truncate ${METADATA_VALUE}`}>
          {name}
        </span>
      )}
      {code && code !== name && (
        <span className={`shrink-0 ${METADATA_EMPTY}`}>({code})</span>
      )}
    </span>
  );
}

/**
 * The footer of both panels: where the record came from, then where to go.
 *
 * Below the rule rather than above it, because provenance is not another
 * field of the specimen — it is the citation, and a citation belongs with the
 * links it is a citation for.
 *
 * Two lines, holder first, then aggregator. They answer different questions
 * and a reader who cannot tell them apart will cite the wrong one: "Specimen
 * Holder" is the museum or herbarium with the physical drawer, and "Source DB"
 * is the database this record was harvested from. The old label — a bare
 * "Institution" sharing one row with the database name — read as two spellings
 * of the same fact, and a long code could wrap into the line below where it no
 * longer looked like a labelled field at all.
 *
 * In this order they read outwards along the provenance chain, from the
 * specimen itself to the aggregator that published it.
 *
 * The three links come last and always together: they leave the page, so they
 * belong after everything that describes the specimen rather than interleaved
 * with it.
 */
export function MetadataLinks({
  meta,
  provenance = null,
  className = "",
}: {
  meta: SpecimenImageMeta;
  provenance?: SpecimenProvenance | null;
  className?: string;
}) {
  const license =
    typeof meta.license === "string" && meta.license.startsWith("http")
      ? meta.license
      : null;
  const imageLink = typeof meta.uri === "string" && meta.uri ? meta.uri : null;

  const sourceDb =
    typeof meta.source_db === "string" && meta.source_db
      ? meta.source_db
      : "GBIF";

  return (
    <div
      className={`mt-1 pt-2 border-t border-deep-mocha-200 dark:border-deep-mocha-700 leading-normal ${className}`}
    >
      {provenance?.institutionCode ? (
        <div className="flex items-baseline gap-1 min-w-0">
          <span className={METADATA_LABEL}>Specimen Holder:</span>
          <SpecimenHolder provenance={provenance} />
        </div>
      ) : null}
      <div className="flex items-baseline gap-1 min-w-0">
        <span className={METADATA_LABEL}>Source DB:</span>
        {/* The aggregator that published the record, not the institution that
            holds the specimen, and not a link: the link to this record is one
            of the three below. */}
        <span className={`truncate uppercase ${METADATA_VALUE}`}>
          {sourceDb}
        </span>
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
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
    </div>
  );
}
