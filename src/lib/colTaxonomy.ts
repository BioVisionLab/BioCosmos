/**
 * Catalogue of Life taxonomy: types, code descriptions, and normalization.
 *
 * The backend serves the authored description of every update-status and
 * match-method code from `GET /taxonomy/codes`, which mirrors the enums in
 * `packages/colharmonize`. Fetching them once keeps per-row payloads down to
 * bare codes and avoids a third hand-maintained copy of the prose here; the
 * fallback map below only covers the case where that request fails.
 */

// The palette moved to ./codeTone so the geography status can share it;
// re-exported here because every existing importer reaches for it via this
// module.
import type { CodeTone } from "./codeTone";

export { toneClasses } from "./codeTone";
export type { CodeTone } from "./codeTone";

/**
 * The Catalogue of Life release the taxonomy on this site was reconciled
 * against.
 *
 * EDIT THIS ONE CONSTANT when a taxonomic update is performed — it is the only
 * place the release is written down, and every attribution on the site reads
 * it from here. A release named in one component and stale in another is
 * worse than none: a reader cannot tell which classification they are looking
 * at.
 */
export const COL_RELEASE = "v2026-08-26 XR";

export type UpdateStatusCode = "MATCHED" | "AMBIGUOUS" | "UNMATCHED";

export interface TaxonCandidate {
  candidateRank: number;
  acceptedName: string | null;
  acceptedAuthorship: string | null;
  acceptedRank: string | null;
  acceptedFamily: string | null;
  candidateMethod: string | null;
  matchScore: number | null;
  genusDistance: number | null;
  epithetDistance: number | null;
}

/** The taxonomic update for one occurrence. */
export interface TaxonUpdate {
  updateStatus: UpdateStatusCode | null;
  matchMethod: string | null;
  acceptedName: string | null;
  acceptedSpeciesName: string | null;
  displayAcceptedName: string | null;
  acceptedRank: string | null;
  acceptedAuthorship: string | null;
  acceptedFamily: string | null;
  acceptedStatus: string | null;
  /** The name as recorded in the occurrence data. */
  inputName: string | null;
  /**
   * The rank the occurrence recorded, which is not the rank it resolved to.
   * One image of a species may be recorded as a trinomial and another as a
   * binomial, so this belongs to the image rather than to the taxon.
   */
  recordedRank: string | null;
  matchScore: number | null;
  scoreMargin: number | null;
  candidateCount: number | null;
  genusChanged: boolean;
  epithetChanged: boolean;
  reasonCode: string | null;
  candidates: TaxonCandidate[];
}

/** A Catalogue of Life classification. */
export interface ColTaxonomy {
  colId: string | null;
  scientificName: string;
  /** The queried name, present only when it differs from the accepted one. */
  inputName: string | null;
  acceptedName: string | null;
  acceptedRank: string | null;
  authorship: string;
  taxonomicStatus: string;
  vernacularName: string;

  kingdom: string;
  phylum: string;
  subphylum: string | null;
  class: string;
  subclass: string | null;
  order: string;
  suborder: string | null;
  superfamily: string | null;
  family: string;
  subfamily: string | null;
  tribe: string | null;
  subtribe: string | null;
  genus: string;
  subgenus: string | null;
  species: string;

  extinct: boolean | null;
  environment: string | null;
  colLink: string | null;
}

/**
 * Ranks the classification table renders, coarsest first.
 *
 * CoL supplies the intermediate ranks GBIF never did. It populates them
 * unevenly across groups, so only the core ranks are always shown; the rest
 * appear when there is something to show.
 */
export const COL_RANK_ORDER = [
  "kingdom",
  "phylum",
  "subphylum",
  "class",
  "subclass",
  "order",
  "suborder",
  "superfamily",
  "family",
  "subfamily",
  "tribe",
  "subtribe",
  "genus",
  "subgenus",
  "species",
] as const;

export type ColRank = (typeof COL_RANK_ORDER)[number];

export const CORE_COL_RANKS: ReadonlySet<string> = new Set([
  "kingdom",
  "phylum",
  "class",
  "order",
  "family",
  "genus",
  "species",
]);

export const ITALIC_COL_RANKS: ReadonlySet<string> = new Set([
  "genus",
  "subgenus",
  "species",
]);

// ---------------------------------------------------------------------------
// Code descriptions
// ---------------------------------------------------------------------------

export interface CodeDescriptions {
  updateStatus: Record<string, string>;
  matchMethod: Record<string, string>;
  reasonCode: Record<string, string>;
}

/**
 * Used only when `/api/taxonomy/codes` cannot be reached, so a hint still
 * explains itself offline. The server response always wins.
 */
const FALLBACK_DESCRIPTIONS: CodeDescriptions = {
  updateStatus: {
    MATCHED: "One accepted taxon was resolved with sufficient evidence.",
    AMBIGUOUS:
      "Candidates were found, but the evidence did not identify one accepted taxon.",
    UNMATCHED:
      "No eligible accepted taxon was found, or the input was invalid or unsupported.",
  },
  matchMethod: {},
  reasonCode: {},
};

let descriptionsPromise: Promise<CodeDescriptions> | null = null;

/**
 * Fetch the code descriptions once per page load.
 *
 * Cached in a module-level promise so the fifty status badges on a search
 * results page share a single request.
 */
export function fetchCodeDescriptions(): Promise<CodeDescriptions> {
  if (!descriptionsPromise) {
    descriptionsPromise = fetch("/api/taxonomy/codes", {
      headers: { Accept: "application/json" },
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => ({
        updateStatus: data?.updateStatus ?? {},
        matchMethod: data?.matchMethod ?? {},
        reasonCode: data?.reasonCode ?? {},
      }))
      .catch((error) => {
        console.error("Failed to fetch taxonomy code descriptions:", error);
        // Do not cache the failure: a later badge can try again.
        descriptionsPromise = null;
        return FALLBACK_DESCRIPTIONS;
      });
  }
  return descriptionsPromise;
}

export type CodeKind = "status" | "method" | "reason";

const CODE_GROUPS: Record<CodeKind, keyof CodeDescriptions> = {
  status: "updateStatus",
  method: "matchMethod",
  reason: "reasonCode",
};

/** Look a code up in a fetched description set. */
export function describeCode(
  code: string | null | undefined,
  kind: CodeKind,
  descriptions: CodeDescriptions | null,
): string | null {
  if (!code || !descriptions) return null;
  return descriptions[CODE_GROUPS[kind]][code.trim().toUpperCase()] ?? null;
}

/**
 * Turn a code into a readable label.
 *
 * `GENUS_SPELLING_EPITHET` becomes "Genus · Spelling epithet" — colharmonize
 * prefixes a method when its species-rank pass found nothing and the match
 * fell through to a coarser rank.
 */
export function humanizeCode(code: string | null | undefined): string {
  if (!code) return "";
  const words = code.trim().toUpperCase().split("_");
  const prefix = words[0];
  const rest =
    prefix === "GENUS" || prefix === "SUBSPECIES" ? words.slice(1) : words;
  const sentence = rest
    .map((word, index) =>
      index === 0
        ? word.charAt(0) + word.slice(1).toLowerCase()
        : word.toLowerCase(),
    )
    .join(" ");
  if (rest.length === words.length) return sentence;
  return `${prefix.charAt(0)}${prefix.slice(1).toLowerCase()} · ${sentence}`;
}

export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "MATCHED":
      return "Matched";
    case "AMBIGUOUS":
      return "Ambiguous";
    case "UNMATCHED":
      return "Unmatched";
    default:
      return "Unknown";
  }
}

/** A shorter label, for the narrow column in the search results table. */
export function statusShortLabel(status: string | null | undefined): string {
  switch (status) {
    case "MATCHED":
      return "Matched";
    case "AMBIGUOUS":
      return "Check";
    case "UNMATCHED":
      return "No match";
    default:
      return "—";
  }
}

export function toneForStatus(status: string | null | undefined): CodeTone {
  switch (status) {
    case "MATCHED":
      return "matched";
    case "AMBIGUOUS":
      return "ambiguous";
    case "UNMATCHED":
      return "unmatched";
    default:
      return "neutral";
  }
}

// ---------------------------------------------------------------------------
// Normalization
// ---------------------------------------------------------------------------

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function optionalText(value: unknown): string | null {
  const trimmed = text(value);
  return trimmed || null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function normalizeCandidate(raw: Record<string, unknown>): TaxonCandidate {
  return {
    candidateRank: optionalNumber(raw.candidateRank) ?? 0,
    acceptedName: optionalText(raw.acceptedName),
    acceptedAuthorship: optionalText(raw.acceptedAuthorship),
    acceptedRank: optionalText(raw.acceptedRank),
    acceptedFamily: optionalText(raw.acceptedFamily),
    candidateMethod: optionalText(raw.candidateMethod),
    matchScore: optionalNumber(raw.matchScore),
    genusDistance: optionalNumber(raw.genusDistance),
    epithetDistance: optionalNumber(raw.epithetDistance),
  };
}

/** Normalize the `taxonomy` block of an image metadata payload. */
export function normalizeTaxonUpdate(raw: unknown): TaxonUpdate | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const status = optionalText(source.updateStatus);
  if (!status) return null;

  const candidates = Array.isArray(source.candidates)
    ? source.candidates
      .filter(
        (entry): entry is Record<string, unknown> =>
          !!entry && typeof entry === "object",
      )
      .map(normalizeCandidate)
    : [];

  return {
    updateStatus: status as UpdateStatusCode,
    matchMethod: optionalText(source.matchMethod),
    acceptedName: optionalText(source.acceptedName),
    acceptedSpeciesName: optionalText(source.acceptedSpeciesName),
    displayAcceptedName: optionalText(source.displayAcceptedName),
    acceptedRank: optionalText(source.acceptedRank),
    acceptedAuthorship: optionalText(source.acceptedAuthorship),
    acceptedFamily: optionalText(source.acceptedFamily),
    acceptedStatus: optionalText(source.acceptedStatus),
    inputName: optionalText(source.inputName),
    recordedRank: optionalText(source.recordedRank),
    matchScore: optionalNumber(source.matchScore),
    scoreMargin: optionalNumber(source.scoreMargin),
    candidateCount: optionalNumber(source.candidateCount),
    genusChanged: source.genusChanged === true,
    epithetChanged: source.epithetChanged === true,
    reasonCode: optionalText(source.reasonCode),
    candidates,
  };
}

/** Normalize the classification returned by the species biology endpoint. */
export function normalizeColTaxonomy(raw: unknown): ColTaxonomy | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const scientificName = text(source.scientificName);
  if (!scientificName) return null;

  return {
    colId: optionalText(source.colId),
    scientificName,
    inputName: optionalText(source.inputName),
    acceptedName: optionalText(source.acceptedName),
    acceptedRank: optionalText(source.acceptedRank),
    authorship: text(source.authorship),
    taxonomicStatus: text(source.taxonomicStatus),
    vernacularName: text(source.vernacularName),
    kingdom: text(source.kingdom),
    phylum: text(source.phylum),
    subphylum: optionalText(source.subphylum),
    // The backend serializes this under the `class` alias.
    class: text(source.class),
    subclass: optionalText(source.subclass),
    order: text(source.order),
    suborder: optionalText(source.suborder),
    superfamily: optionalText(source.superfamily),
    family: text(source.family),
    subfamily: optionalText(source.subfamily),
    tribe: optionalText(source.tribe),
    subtribe: optionalText(source.subtribe),
    genus: text(source.genus),
    subgenus: optionalText(source.subgenus),
    species: text(source.species),
    extinct: typeof source.extinct === "boolean" ? source.extinct : null,
    environment: optionalText(source.environment),
    colLink: optionalText(source.colLink),
  };
}

/** Read one rank off a classification. */
export function rankValue(
  taxonomy: ColTaxonomy,
  rank: ColRank,
): string | null {
  const value = taxonomy[rank as keyof ColTaxonomy];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}
