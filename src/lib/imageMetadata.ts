/**
 * The image metadata payload, shared by the two surfaces that render it:
 * the panel under the species gallery and the specimen image modal.
 *
 * Field names stay snake_case because that is what
 * `/api/images/id/metadata` returns; only the nested `taxonomy` block is
 * camelCase, matching the backend payload it comes from.
 */

import { TaxonUpdate, normalizeTaxonUpdate } from "./colTaxonomy";

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
  [key: string]: unknown;
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
