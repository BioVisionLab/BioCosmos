import React, { useState } from "react";
import NoImage from "@/components/NoImage";
import { CodeHint, CoordinateStatusBadge } from "@/components/CodeHint";
import {
  ADM1_MISMATCH_NOTE,
  type CoordinateValidationStatusCode,
} from "@/lib/geoValidation";
import type { SpecimenRecord } from "@/lib/map";

/**
 * The coordinate's verdict, as the same badge the Image Metadata panel shows,
 * hint included. A record the validation has not reached gets a plain pill in
 * the same shape, so every card still says whether its dot was checked.
 */
function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return (
      <CodeHint
        code="NOT_VALIDATED"
        label="Coordinate not validated"
        description={null}
        tone="unmatched"
      />
    );
  }
  return (
    <CoordinateStatusBadge
      validation={{
        validationStatus: status as CoordinateValidationStatusCode,
      }}
    />
  );
}

/**
 * The card's image slot: a fixed box on the gallery's placeholder surface, so
 * the card keeps one shape whether the thumbnail loads, is still loading, or
 * failed, and the popup's close button (pinned inside the box's corner by
 * `.species-map-popup` in globals.css) sits in the same place either way.
 *
 * The <img> stays invisible until it has loaded, as in the specimens gallery:
 * otherwise the browser paints its broken-image icon and the alt text.
 */
function SpecimenThumbnail({
  imgId,
  alt,
  compact,
}: {
  imgId: string;
  alt: string;
  compact: boolean;
}) {
  const src = `/api/images/id?imageId=${encodeURIComponent(imgId)}&type=thumbnail`;
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const failed = failedSrc === src;

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-lg bg-deep-mocha-100 dark:bg-deep-mocha-900 ${
        compact ? "h-16 w-16" : "h-28 w-full"
      }`}
    >
      {failed ? (
        <NoImage
          className={compact ? "text-[10px] [&>svg]:h-4 [&>svg]:w-4" : ""}
        />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoadedSrc(src)}
          onError={() => setFailedSrc(src)}
          // The full card insets the image on both sides, so it stays
          // centred and clear of the close button in the top-right corner.
          className={`h-full w-full object-contain transition-opacity ${
            compact ? "p-1" : "px-9 py-2"
          } ${loadedSrc === src ? "opacity-100" : "opacity-0"}`}
        />
      )}
    </div>
  );
}

/** "São Paulo, Brazil", finest rank first, or null when neither is known. */
function placeText(adm1: string | null, country: string | null): string | null {
  return [adm1, country].filter(Boolean).join(", ") || null;
}

/**
 * "Dorsal", or "Dorsal, Ventral" for a specimen photographed from both sides:
 * worded as the Image Metadata panel's View row, dorsal first.
 */
function viewText(sides: string[]): string | null {
  const order = ["dorsal", "ventral"];
  const known = order.filter((side) => sides.includes(side));
  const other = sides.filter((side) => !order.includes(side));
  const all = [...known, ...other];
  if (all.length === 0) return null;
  return all
    .map((side) => side.charAt(0).toUpperCase() + side.slice(1))
    .join(", ");
}

/**
 * The popup card for one specimen, shared by the distribution map and the
 * specimens tab's cluster map so the two describe a record the same way.
 * `leadingRows` go above the record's own rows, for what only one map knows,
 * such as the cluster a point belongs to.
 *
 * `compact` sets the thumbnail beside the rows rather than above them, for a
 * hover popup: it cannot pan the map to make room without dragging the map
 * away from the cursor, so it has to fit above or below the point as it is.
 */
export function SpecimenRecordCard({
  record,
  leadingRows = [],
  compact = false,
}: {
  record: SpecimenRecord;
  leadingRows?: [string, React.ReactNode][];
  compact?: boolean;
}) {
  const museum = record.institutionName
    ? record.institutionCode
      ? `${record.institutionName} (${record.institutionCode})`
      : record.institutionName
    : (record.institutionCode ?? record.sourceDb);
  const recorded = placeText(record.recordedAdm1, record.recordedCountry);
  const reference = placeText(record.referenceAdm1, record.referenceCountry);
  // A coordinate that agrees with its record needs one locality. Any other
  // status sets the record beside where the dot actually falls, so a
  // mismatch can be read off the card rather than taken on trust.
  const localityRows: [string, React.ReactNode][] =
    record.validationStatus === "VALID"
      ? [["Locality", recorded ?? reference]]
      : [
          ["Recorded", recorded],
          ["Coordinate in", reference],
        ];
  const rows: [string, React.ReactNode][] = [
    ...leadingRows,
    ["Specimen ID", record.catalogNumber],
    ["View", viewText(record.sides)],
    ["Museum", museum],
    ...localityRows,
  ];

  const thumbnail = (
    <SpecimenThumbnail
      imgId={record.imgId}
      alt={`Specimen ${record.catalogNumber ?? record.imgId}`}
      compact={compact}
    />
  );

  const details = (
    <>
      <dl
        className={`grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 ${compact ? "" : "mt-2"}`}
      >
        {rows
          .filter(([, value]) => value !== null && value !== "")
          .map(([label, value]) => (
            <React.Fragment key={label}>
              <dt className="text-deep-mocha-500 dark:text-deep-mocha-400">
                {label}
              </dt>
              <dd className="break-words">{value}</dd>
            </React.Fragment>
          ))}
      </dl>
      {record.validationStatus === "ADM1_MISMATCH" ? (
        <p className="mt-1.5 text-[0.7rem] text-deep-mocha-500 dark:text-deep-mocha-400">
          {ADM1_MISMATCH_NOTE}
        </p>
      ) : null}
      <div className="mt-2">
        <StatusBadge status={record.validationStatus} />
      </div>
    </>
  );

  if (compact) {
    return (
      <div className="w-72 flex gap-3 text-xs text-deep-mocha-900 dark:text-deep-mocha-100">
        {thumbnail}
        <div className="min-w-0 flex-1">{details}</div>
      </div>
    );
  }

  return (
    <div className="w-52 text-xs text-deep-mocha-900 dark:text-deep-mocha-100">
      {thumbnail}
      {details}
    </div>
  );
}
