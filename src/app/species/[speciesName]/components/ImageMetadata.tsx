"use client";
import React, { useEffect, useId, useRef, useState } from "react";
import { NoData } from "@/components/NoData";
import {
  CodeHint,
  CoordinateStatusBadge,
  TaxonStatusBadge,
} from "@/components/CodeHint";
import { TaxonCandidate, TaxonUpdate } from "@/lib/colTaxonomy";
import {
  SpecimenImageMeta,
  acceptedDisplayName,
  coordinatesOf,
  localityOf,
  nameWasUpdated,
  taxonomyOf,
} from "@/lib/imageMetadata";
import { SpecimenLocality } from "@/lib/geoValidation";
import {
  METADATA_EMPTY,
  METADATA_LABEL,
  METADATA_VALUE,
  MatchingHelpLink,
  MetadataLinks,
} from "@/components/ImageMetadataFields";
import { cleanSpeciesName } from "@/lib/names";

interface ImageMetadataProps {
  speciesName?: string;
  imageId?: string | null;
  prevImageIds?: string[];
  nextImageIds?: string[];
}

/**
 * The runner-up matches Catalogue of Life could have resolved the name to.
 *
 * Collapsed by default: for a decisive match these are noise, and for an
 * ambiguous one they are the whole point.
 */
function AlternativeCandidates({
  candidates,
}: {
  candidates: TaxonCandidate[];
}) {
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  if (!candidates.length) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            // Keep Escape from also closing a surrounding modal.
            event.stopPropagation();
            setOpen(false);
            triggerRef.current?.focus();
          }
        }}
        className="w-fit text-left text-xs underline decoration-dotted underline-offset-2 text-deep-mocha-600 dark:text-deep-mocha-400 hover:text-deep-mocha-800 dark:hover:text-deep-mocha-200 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-hunter-green-500 rounded-xs"
      >
        {open ? "Hide" : "Show"} alternative candidates ({candidates.length})
      </button>
      <ol
        id={panelId}
        className={
          open
            ? "list-decimal pl-5 space-y-1.5 text-xs text-deep-mocha-600 dark:text-deep-mocha-400"
            : "hidden"
        }
        aria-hidden={!open}
      >
        {candidates.map((candidate) => (
          <li key={`${candidate.candidateRank}-${candidate.acceptedName}`}>
            <span className="flex flex-wrap items-baseline gap-x-1.5 gap-y-1">
              <i className="italic">{candidate.acceptedName ?? "—"}</i>
              {candidate.acceptedAuthorship ? (
                <span className="text-deep-mocha-500">
                  {candidate.acceptedAuthorship}
                </span>
              ) : null}
              {candidate.acceptedRank ? (
                <span className="text-deep-mocha-500">
                  {candidate.acceptedRank}
                </span>
              ) : null}
              {candidate.candidateMethod ? (
                <CodeHint code={candidate.candidateMethod} kind="method" />
              ) : null}
              {candidate.matchScore !== null ? (
                <span className="text-deep-mocha-500">
                  score {candidate.matchScore}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function LocalityBlock({ locality }: { locality: SpecimenLocality | null }) {
  // Unlike the taxonomy block, this row is rendered even when empty: a
  // locality is expected on most specimens, so a missing row would read as a
  // bug rather than as an absence.
  return (
    <div className="col-span-2 flex flex-wrap items-baseline gap-1 min-w-0 leading-normal">
      <span className="whitespace-nowrap">Locality:</span>
      {locality?.display ? (
        <span className={`min-w-0 ${METADATA_VALUE}`}>
          {locality.display}
        </span>
      ) : (
        <span className={METADATA_EMPTY}>—</span>
      )}
      {/* The unparsed original, and only when it says something the parsed
          ranks do not already. */}
      {locality?.verbatimLocality &&
      locality.verbatimLocality !== locality.locality ? (
        <span className="text-deep-mocha-500">
          (as recorded: {locality.verbatimLocality})
        </span>
      ) : null}
    </div>
  );
}

function TaxonomyBlock({ update }: { update: TaxonUpdate }) {
  const accepted = acceptedDisplayName(update);
  const showRecorded = nameWasUpdated(update);

  return (
    // The card sets a very tight leading for its one-line rows; this block is
    // multi-line, so it sets its own.
    <div className="col-span-2 mt-1 pt-2 border-t border-deep-mocha-200 dark:border-deep-mocha-700 flex flex-col gap-1.5 leading-normal">
      <div className="flex flex-wrap items-start gap-2">
        <span className="whitespace-nowrap">Taxonomy:</span>
        <TaxonStatusBadge update={update} showMethod />
        <MatchingHelpLink
          section="taxonomy-matching"
          label="How taxonomy matching works"
        />
      </div>

      {accepted ? (
        <div className="flex flex-wrap items-baseline gap-1 min-w-0">
          <span className="whitespace-nowrap">Accepted name:</span>
          <i className="italic">{accepted}</i>
          {update.acceptedAuthorship ? (
            <span className="text-deep-mocha-500">
              {update.acceptedAuthorship}
            </span>
          ) : null}
        </div>
      ) : null}

      {showRecorded && update.inputName ? (
        // Per image, not per species: the gallery on one species page can hold
        // a trinomial, a binomial and an outright different name, and only the
        // selected image's own wording belongs here.
        <div className="flex flex-wrap items-baseline gap-1 min-w-0">
          <span className="whitespace-nowrap">Recorded as:</span>
          <i className="italic text-deep-mocha-500">
            {cleanSpeciesName(update.inputName)}
          </i>
          {/* Only when it says something the name does not already: almost
              every occurrence is recorded at species rank. */}
          {update.recordedRank &&
          update.recordedRank.toLowerCase() !== "species" ? (
            <span className="text-deep-mocha-500">
              ({update.recordedRank.toLowerCase()})
            </span>
          ) : null}
        </div>
      ) : null}

      {update.reasonCode ? (
        <div className="flex flex-wrap items-center gap-1">
          <span className="whitespace-nowrap">Reason:</span>
          <CodeHint code={update.reasonCode} kind="reason" />
        </div>
      ) : null}

      <AlternativeCandidates candidates={update.candidates} />
    </div>
  );
}

export default function ImageMetadata({
  imageId,
  prevImageIds,
  nextImageIds,
}: ImageMetadataProps) {
  const [meta, setMeta] = useState<SpecimenImageMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const cacheRef = React.useRef<Map<string, SpecimenImageMeta | null>>(
    new Map(),
  );

  // Helper to fetch metadata and store in cache
  const fetchAndCache = async (id: string) => {
    try {
      const res = await fetch(
        `/api/images/id/metadata?imageId=${encodeURIComponent(id)}`,
      );
      if (!res.ok) return null;
      const data = await res.json();
      cacheRef.current.set(id, data ?? null);
      return data ?? null;
    } catch (err) {
      console.error("Error fetching image metadata:", err);
      return null;
    }
  };

  // Main effect: when imageId changes, display from cache if available otherwise fetch
  useEffect(() => {
    if (!imageId) {
      setMeta(null);
      setLoading(false);
      return;
    }

    let ignore = false;

    const run = async () => {
      const cached = cacheRef.current.get(imageId);
      if (cached !== undefined) {
        setMeta(cached);
        setLoading(false);
        return;
      }

      setMeta(null);
      setLoading(true);
      const data = await fetchAndCache(imageId);
      if (!ignore) setMeta(data);
      if (!ignore) setLoading(false);
    };

    void run();
    return () => {
      ignore = true;
    };
  }, [imageId]);

  // Prefetch neighbor metadata in background (up to two in either direction)
  useEffect(() => {
    const toPrefetch: Array<string | undefined | null> = [];
    if (prevImageIds && prevImageIds.length)
      toPrefetch.push(...prevImageIds.slice(-2));
    if (nextImageIds && nextImageIds.length)
      toPrefetch.push(...nextImageIds.slice(0, 2));
    toPrefetch.forEach((id) => {
      if (!id) return;
      if (cacheRef.current.has(id)) return;
      void fetchAndCache(id);
    });
  }, [prevImageIds, nextImageIds]);

  const taxonomy = taxonomyOf(meta);
  const locality = localityOf(meta);
  const coordinates = coordinatesOf(meta);

  return (
    <div className="p-5 bg-deep-mocha-100 dark:bg-deep-mocha-900 border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl text-sm text-deep-mocha-700 dark:text-deep-mocha-400 leading-3.5">
      <h3 className="text-base font-semibold mb-2">Image Metadata</h3>
      <div className="flex flex-col gap-1">
        {loading ? (
          <div className="text-center text-sm text-deep-mocha-500">
            Loading metadata…
          </div>
        ) : !meta ? (
          <NoData
            text={imageId ? "No metadata available." : "No image selected."}
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 items-start">
              {/* Left column: View, Source DB, Coordinates */}
              <div className="flex items-center min-w-0">
                <span className={METADATA_LABEL}>
                  View:
                </span>
                <span className={`ml-1 truncate capitalize ${METADATA_VALUE}`}>
                  {typeof meta.class_dv === "string"
                    ? meta.class_dv.toLowerCase()
                    : "—"}
                </span>
              </div>
              <div className="flex items-center min-w-0">
                <span className={METADATA_LABEL}>
                  Source DB:
                </span>
                {/* The name of the database, not a link: the link to this
                    record lives with the other two at the bottom. */}
                <span className={`ml-1 truncate uppercase ${METADATA_VALUE}`}>
                  {typeof meta.source_db === "string" && meta.source_db
                    ? meta.source_db
                    : "GBIF"}
                </span>
              </div>

              {/* Locality first, then the coordinate and the verdict on it:
                  the written record, then the check against it. The specimen
                  modal shows the same two in the same order. */}
              <LocalityBlock locality={locality} />

              <div className="flex items-center min-w-0">
                <span className={METADATA_LABEL}>
                  Coordinates:
                </span>
                <span className={`ml-1 truncate ${METADATA_VALUE}`}>
                  {meta.lat || meta.lon
                    ? `${meta.lat ?? "—"}, ${meta.lon ?? "—"}`
                    : "—"}
                </span>
              </div>
              <div className="flex items-center gap-1.5 min-w-0">
                {coordinates ? (
                  <>
                    <CoordinateStatusBadge validation={coordinates} />
                    <MatchingHelpLink
                      section="coordinate-matching"
                      label="How coordinate matching works"
                    />
                  </>
                ) : null}
              </div>

              {/* Omitted entirely when no harmonization run has been loaded,
                  rather than shown as a row of placeholders. */}
              {taxonomy ? <TaxonomyBlock update={taxonomy} /> : null}

              <MetadataLinks meta={meta} className="col-span-2" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
