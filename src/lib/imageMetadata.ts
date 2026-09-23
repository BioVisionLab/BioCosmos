/**
 * The image metadata payload, shared by the two surfaces that render it:
 * the panel under the species gallery and the specimen image modal.
 *
 * Field names stay snake_case because that is what
 * `/api/images/id/metadata` returns; only the nested `taxonomy` block is
 * camelCase, matching the backend payload it comes from.
 */

import { TaxonUpdate, normalizeTaxonUpdate } from "./colTaxonomy";
import {
  CoordinateValidation,
  SpecimenLocality,
  normalizeCoordinateValidation,
  normalizeSpecimenLocality,
} from "./geoValidation";

export interface SpecimenImageMeta {
  class_dv?: string | null;
  lat?: number | null;
  lon?: number | null;
  source_db?: string | null;
  license?: string | null;
  uuid?: string | null;
  uri?: string | null;
  /** The species name as recorded in the occurrence data. */
  species?: string | null;
  /** Absent until a colharmonize run has been loaded. */
  taxonomy?: unknown;
  /** Absent until the locality table has been built. */
  locality?: unknown;
  /** Absent until `geoharmonize integrate` has been run. */
  coordinates?: unknown;
  /** Absent until the provenance table has been built. */
  provenance?: unknown;
  [key: string]: unknown;
}

/** The holding institution and the specimen's own catalog number. */
export interface SpecimenProvenance {
  institutionCode: string | null;
  catalogNumber: string | null;
  /** The code's full name, when instharmonize resolved it. */
  institutionName: string | null;
  /** The institution's website, already checked to be http(s). */
  institutionHomepage: string | null;
}

/**
 * Read the taxonomic update off a metadata payload.
 *
 * Returns null when no run has been loaded, so callers can omit the block
 * rather than render empty rows.
 */
export function taxonomyOf(
  meta: SpecimenImageMeta | null | undefined,
): TaxonUpdate | null {
  if (!meta) return null;
  return normalizeTaxonUpdate(meta.taxonomy);
}

/**
 * What to show in place of the recorded name: the accepted binomial, else the
 * genus the match resolved to, else nothing.
 */
export function acceptedDisplayName(
  update: TaxonUpdate | null,
): string | null {
  if (!update) return null;
  return update.displayAcceptedName ?? update.acceptedSpeciesName ?? null;
}

/** Whether the accepted name differs from the name that was recorded. */
export function nameWasUpdated(update: TaxonUpdate | null): boolean {
  if (!update?.inputName) return false;
  const accepted = acceptedDisplayName(update);
  if (!accepted) return true;
  const normalize = (value: string) =>
    value.replace(/_/g, " ").trim().toLowerCase();
  return normalize(update.inputName) !== normalize(accepted);
}

/**
 * Read the written locality off a metadata payload.
 *
 * Returns null when nothing was recorded, so callers can omit the block
 * rather than render empty rows.
 */
export function localityOf(
  meta: SpecimenImageMeta | null | undefined,
): SpecimenLocality | null {
  if (!meta) return null;
  return normalizeSpecimenLocality(meta.locality);
}

/** Read the coordinate validation off a metadata payload. */
export function coordinatesOf(
  meta: SpecimenImageMeta | null | undefined,
): CoordinateValidation | null {
  if (!meta) return null;
  return normalizeCoordinateValidation(meta.coordinates);
}

/**
 * Read the institution and specimen identifier off a metadata payload.
 *
 * Returns null when neither field was recorded, so callers can omit the
 * block rather than render two empty rows.
 */
export function provenanceOf(
  meta: SpecimenImageMeta | null | undefined,
): SpecimenProvenance | null {
  const raw = meta?.provenance;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const institutionCode =
    typeof obj.institutionCode === "string" ? obj.institutionCode : null;
  const catalogNumber =
    typeof obj.catalogNumber === "string" ? obj.catalogNumber : null;
  if (!institutionCode && !catalogNumber) return null;
  const institutionName =
    typeof obj.institutionName === "string" && obj.institutionName.trim()
      ? obj.institutionName
      : null;
  return {
    institutionCode,
    catalogNumber,
    institutionName,
    // A website without a name would have nothing to hang on.
    institutionHomepage: institutionName
      ? safeWebUrl(obj.institutionHomepage)
      : null,
  };
}

/**
 * Where "Source Link" points: the occurrence record in its own database.
 *
 * `uuid` holds a full URL for most sources and a bare identifier for others,
 * so anything that does not parse as an http(s) URL falls back to GBIF rather
 * than producing a dead — or hostile — link. The protocol is checked after
 * parsing, not just matched at the front, so a crafted value cannot smuggle
 * another scheme through.
 */
export function sourceDbHref(
  rawUrl: unknown,
  fallback = "https://www.gbif.org",
): string {
  return safeWebUrl(rawUrl) ?? fallback;
}

/**
 * An http(s) URL safe to put in an href, or null.
 *
 * A bare `www.` host is given https. The protocol is checked after parsing,
 * not just matched at the front, so a crafted value cannot smuggle another
 * scheme through.
 */
export function safeWebUrl(rawUrl: unknown): string | null {
  if (typeof rawUrl !== "string") return null;
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;

  const normalized = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : /^www\./i.test(trimmed)
      ? `https://${trimmed}`
      : "";
  if (!normalized) return null;

  try {
    const parsed = new URL(normalized);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
    return null;
  } catch {
    return null;
  }
}
