/**
 * Coordinate validation against GADM: types, code descriptions, normalization.
 *
 * The backend serves the authored description of every code from
 * `GET /geography/codes`, mirroring the enums in `packages/geoharmonize`, so
 * per-row payloads carry bare codes and the prose has one home. The fallback
 * map below only covers the case where that request fails.
 */

import type { CodeTone } from "./codeTone";
import { humanizeCode } from "./colTaxonomy";

export { toneClasses } from "./codeTone";
export type { CodeTone } from "./codeTone";

export type CoordinateValidationStatusCode =
  | "MISSING_COORDINATE"
  | "COORDINATE_OUT_OF_RANGE"
  | "ZERO_COORDINATE"
  | "NO_REFERENCE_MATCH"
  | "AMBIGUOUS_REFERENCE"
  | "COUNTRY_MISMATCH"
  | "ADM1_MISMATCH"
  | "VALID";

/** The written locality of one occurrence, as recorded rather than derived. */
export interface SpecimenLocality {
  /**
   * The ranks joined coarsest-first, built by the backend so the species
   * panel, the modal and the search table cannot disagree about the wording.
   */
  display: string | null;
  country: string | null;
  countryCode: string | null;
  stateProvince: string | null;
  county: string | null;
  municipality: string | null;
  locality: string | null;
  verbatimLocality: string | null;
}

/** How one occurrence's coordinate compares to the locality it records. */
export interface CoordinateValidation {
  validationStatus: CoordinateValidationStatusCode | null;
  coordinateCheck: string | null;
  countryCheck: string | null;
  adm1Check: string | null;
  recordedCountry: string | null;
  recordedAdm1: string | null;
  /** Null unless exactly one GADM region matched the coordinate. */
  referenceCountry: string | null;
  referenceAdm1: string | null;
  runId: string | null;
  gadmSha256: string | null;
}

// ---------------------------------------------------------------------------
// Code descriptions
// ---------------------------------------------------------------------------

export interface GeoCodeDescriptions {
  validationStatus: Record<string, string>;
  coordinateCheck: Record<string, string>;
  countryCheck: Record<string, string>;
  adm1Check: Record<string, string>;
}

export type GeoCodeKind =
  | "validationStatus"
  | "coordinateCheck"
  | "countryCheck"
  | "adm1Check";

/**
 * Used only when `/api/geography/codes` cannot be reached, so a hint still
 * explains itself offline. The server response always wins.
 */
const FALLBACK_GEO_DESCRIPTIONS: GeoCodeDescriptions = {
  validationStatus: {
    VALID: "The coordinate passed all applicable checks.",
    COUNTRY_MISMATCH:
      "The recorded country disagreed with the coordinate-derived country.",
    ADM1_MISMATCH:
      "The recorded ADM1 disagreed with the coordinate-derived ADM1.",
    NO_REFERENCE_MATCH: "The coordinate intersected no GADM region.",
    AMBIGUOUS_REFERENCE:
      "The coordinate intersected multiple distinct GADM regions.",
    ZERO_COORDINATE: "The coordinate pair was 0,0.",
    COORDINATE_OUT_OF_RANGE:
      "Latitude or longitude was outside its valid geographic range.",
    MISSING_COORDINATE: "Latitude or longitude was missing or invalid.",
  },
  coordinateCheck: {},
  countryCheck: {},
  adm1Check: {},
};

let geoDescriptionsPromise: Promise<GeoCodeDescriptions> | null = null;

/**
 * Fetch the code descriptions once per page load.
 *
 * Cached in a module-level promise so the fifty status badges on a search
 * results page share a single request.
 */
export function fetchGeoCodeDescriptions(): Promise<GeoCodeDescriptions> {
  if (!geoDescriptionsPromise) {
    geoDescriptionsPromise = fetch("/api/geography/codes", {
      headers: { Accept: "application/json" },
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => ({
        validationStatus: data?.validationStatus ?? {},
        coordinateCheck: data?.coordinateCheck ?? {},
        countryCheck: data?.countryCheck ?? {},
        adm1Check: data?.adm1Check ?? {},
      }))
      .catch((error) => {
        console.error("Failed to fetch geography code descriptions:", error);
        // Do not cache the failure: a later badge can try again.
        geoDescriptionsPromise = null;
        return FALLBACK_GEO_DESCRIPTIONS;
      });
  }
  return geoDescriptionsPromise;
}

/** Look a code up in a fetched description set. */
export function describeGeoCode(
  code: string | null | undefined,
  kind: GeoCodeKind,
  descriptions: GeoCodeDescriptions | null,
): string | null {
  if (!code || !descriptions) return null;
  return descriptions[kind][code.trim().toUpperCase()] ?? null;
}

// ---------------------------------------------------------------------------
// Labels and tone
// ---------------------------------------------------------------------------

/**
 * Shown beside a state mismatch. Many are not misplaced coordinates at all:
 * the record names its state in a form GADM does not use, such as "East
 * Kalimantan" for Kalimantan Timur, and the names fail to match.
 */
export const ADM1_MISMATCH_NOTE =
  "The record may use a non-standard state name, such as an English or older name.";

export function coordinateStatusLabel(
  status: string | null | undefined,
): string {
  switch (status) {
    case "VALID":
      return "Valid";
    case "COUNTRY_MISMATCH":
      return "Country mismatch";
    case "ADM1_MISMATCH":
      return "State mismatch";
    case "NO_REFERENCE_MATCH":
      return "No region matched";
    case "AMBIGUOUS_REFERENCE":
      return "Ambiguous region";
    case "ZERO_COORDINATE":
      return "Zero coordinate";
    case "COORDINATE_OUT_OF_RANGE":
      return "Out of range";
    case "MISSING_COORDINATE":
      return "No coordinate";
    default:
      return status ? humanizeCode(status) : "Unknown";
  }
}

/** A shorter label, for the narrow column in the search results table. */
export function coordinateStatusShortLabel(
  status: string | null | undefined,
): string {
  switch (status) {
    case "VALID":
      return "Valid";
    case "COUNTRY_MISMATCH":
      return "Country";
    case "ADM1_MISMATCH":
      return "State";
    case "NO_REFERENCE_MATCH":
      return "No region";
    case "AMBIGUOUS_REFERENCE":
      return "Ambiguous";
    case "ZERO_COORDINATE":
      return "0, 0";
    case "COORDINATE_OUT_OF_RANGE":
      return "Out of range";
    default:
      return "—";
  }
}

/**
 * Four of the eight outcomes are not failures of the data but of the check:
 * no region, several regions. Those read as neutral rather than as an error,
 * while a zero or out-of-range coordinate is simply wrong.
 */
export function toneForCoordinateStatus(
  status: string | null | undefined,
): CodeTone {
  switch (status) {
    case "VALID":
      return "matched";
    case "COUNTRY_MISMATCH":
    case "ADM1_MISMATCH":
      return "ambiguous";
    case "ZERO_COORDINATE":
    case "COORDINATE_OUT_OF_RANGE":
      return "invalid";
    case "MISSING_COORDINATE":
      return "unmatched";
    default:
      return "neutral";
  }
}

// ---------------------------------------------------------------------------
// Normalization
// ---------------------------------------------------------------------------

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function normalizeSpecimenLocality(
  raw: unknown,
): SpecimenLocality | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const locality: SpecimenLocality = {
    display: text(source.display),
    country: text(source.country),
    countryCode: text(source.countryCode),
    stateProvince: text(source.stateProvince),
    county: text(source.county),
    municipality: text(source.municipality),
    locality: text(source.locality),
    verbatimLocality: text(source.verbatimLocality),
  };
  const hasAny = Object.values(locality).some((value) => value !== null);
  return hasAny ? locality : null;
}

export function normalizeCoordinateValidation(
  raw: unknown,
): CoordinateValidation | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const status = text(source.validationStatus);
  if (!status) return null;
  return {
    validationStatus: status as CoordinateValidationStatusCode,
    coordinateCheck: text(source.coordinateCheck),
    countryCheck: text(source.countryCheck),
    adm1Check: text(source.adm1Check),
    recordedCountry: text(source.recordedCountry),
    recordedAdm1: text(source.recordedAdm1),
    referenceCountry: text(source.referenceCountry),
    referenceAdm1: text(source.referenceAdm1),
    runId: text(source.runId),
    gadmSha256: text(source.gadmSha256),
  };
}

/**
 * Rebuild the one-line locality from the flat columns of a search row.
 *
 * The metadata endpoint sends a `display` string it built itself; the search
 * payload is flat, so the table assembles its own from the same rank order.
 * Empty parts are skipped, and a part repeating one already written is
 * dropped — publishers routinely set municipality and locality to one string.
 */
export function localityLine(
  parts: Array<string | null | undefined>,
): string | null {
  const seen = new Set<string>();
  const kept: string[] = [];
  for (const part of parts) {
    if (!part || !part.trim()) continue;
    // Accents are stripped as well as punctuation: one GBIF record can carry
    // "Sao Paulo" and "São Paulo" in adjacent ranks, and they are one place.
    const key = part
      .normalize("NFKD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    kept.push(part.trim());
  }
  return kept.length ? kept.join(", ") : null;
}
