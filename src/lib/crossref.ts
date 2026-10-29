/*
Literature search via CrossRef.

The search itself runs in the backend (`/species/{name}/literature`), which
queries CrossRef under the accepted name and every Catalogue of Life synonym,
and adds papers on the genus when the species has too few of its own. This
module only fetches that result and prepares it for display.
*/
import { ORDER_NAME } from "./taxonSlug";
import {
  decodeHtmlEntities,
  toAuthorNameCase,
  toSentenceCase,
} from "./textUtils";

export interface CrossRefResult {
  title: string;
  /** The CrossRef work type, e.g. "journal-article" or "dataset". */
  publicationType?: string;
  authors: string[];
  published_year?: number;
  journal: string;
  volume?: string;
  issue?: string;
  pages?: string;
  doi: string | null;
  /** Species tier: the name the paper was found under. */
  matchedName?: string;
  /** Species tier: whether that name is the accepted one or a synonym. */
  matchedVia?: "accepted" | "synonym";
  /** Genus tier: the other species of the genus the paper names. */
  mentions: string[];
}

/* The bracketed description a citation adds after the title, by CrossRef type. */
const citationTypeTags: Record<string, string> = {
  dataset: "Dataset",
  "posted-content": "Preprint",
  dissertation: "Dissertation",
  report: "Report",
};

/**
 * A plain-text citation for the clipboard, in the order the page shows it:
 * authors, year, title, journal, volume (issue), pages, DOI. Publisher markup
 * in the title (`<i>` around a species name) is dropped.
 */
export function formatCitation(pub: CrossRefResult): string {
  const title = pub.title.replace(/<[^>]+>/g, "").trim();
  const tag = pub.publicationType
    ? citationTypeTags[pub.publicationType]
    : undefined;
  const parts = [
    pub.authors.length ? `${pub.authors.join(", ")}.` : "",
    pub.published_year ? `(${pub.published_year}).` : "",
    title ? `${title.replace(/\.$/, "")}${tag ? ` [${tag}]` : ""}.` : "",
  ];
  let source = pub.journal;

  if (pub.volume) source += `, ${pub.volume}`;

  if (pub.issue) source += ` (${pub.issue})`;

  if (pub.pages) source += `, pp. ${pub.pages}`;

  parts.push(source ? `${source}.` : "");

  if (pub.doi) parts.push(pub.doi);

  return parts.filter(Boolean).join(" ");
}

/** Publications keyed by year ("Unknown Year" when CrossRef has none). */
export type PublicationsByYear = Record<string, CrossRefResult[]>;

export interface LiteratureResult {
  acceptedName: string;
  genus: string | null;
  synonymsSearched: string[];
  species: PublicationsByYear;
  speciesCount: number;
  /** Null when the species had enough papers that the genus was not searched. */
  genusRelated: PublicationsByYear | null;
  genusRelatedCount: number;
  /** The species-paper count below which the genus section is added. */
  minSpeciesResults: number;
  /** True when some CrossRef requests failed, so the lists may be incomplete. */
  partial: boolean;
  /** The earliest publication year searched; null when every year is. */
  fromYear: number | null;
}

interface ApiWork {
  title: string;
  publicationType: string | null;
  authors: string[];
  publishedYear: number | null;
  journal: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  doi: string | null;
  matchedName: string | null;
  matchedVia: "accepted" | "synonym" | null;
  mentions: string[];
}

interface ApiPayload {
  acceptedName: string;
  genus: string | null;
  synonymsSearched: string[];
  species: ApiWork[];
  genusRelated: ApiWork[] | null;
  minSpeciesResults: number;
  partial: boolean;
  fromYear: number | null;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Sentence-case a title, then put back the capital on the genera we know.
 *
 * Titles arrive in whatever case the publisher deposited, often Title Case or
 * ALL CAPS, so they are normalized to sentence case for a consistent list —
 * which would otherwise also lower-case the genus names the page is about.
 */
function formatTitle(raw: string, genera: string[]): string {
  // Keep only the italic markup the title renderer understands; drop other
  // inline tags publishers deposit (<scp>, <sub>, <b>, ...). Named tags only,
  // so a literal "<Genus species>" in a title is left alone.
  const cleaned = decodeHtmlEntities(raw).replace(
    /<\/?(?:b|u|sc|scp|sub|sup|span|strong|mml:[a-z]+)\b[^>]*>/gi,
    "",
  );
  let title = toSentenceCase(cleaned);

  for (const genus of genera) {
    title = title.replace(
      new RegExp(`\\b${escapeRegExp(genus)}\\b`, "gi"),
      genus,
    );
  }

  return title;
}

function toResult(work: ApiWork, genera: string[]): CrossRefResult {
  return {
    title: formatTitle(work.title, genera),
    publicationType: work.publicationType ?? undefined,
    authors: work.authors.length
      ? work.authors.map((a) => toAuthorNameCase(a))
      : ["No authors available"],
    published_year: work.publishedYear ?? undefined,
    journal: decodeHtmlEntities(work.journal ?? "No journal available"),
    volume: work.volume ?? undefined,
    issue: work.issue ?? undefined,
    pages: work.pages ?? undefined,
    doi: work.doi,
    matchedName: work.matchedName ?? undefined,
    matchedVia: work.matchedVia ?? undefined,
    mentions: work.mentions ?? [],
  };
}

/* Group by year so the list is not cluttered for viewing. */
function groupByYear(works: CrossRefResult[]): PublicationsByYear {
  const grouped: PublicationsByYear = {};

  for (const work of works) {
    const key = work.published_year
      ? String(work.published_year)
      : "Unknown Year";
    (grouped[key] ??= []).push(work);
  }

  return grouped;
}

/** The genus of each binomial, deduplicated. */
function generaOf(names: (string | null | undefined)[]): string[] {
  const genera = names
    .map((name) => name?.trim().split(/\s+/)[0])
    .filter((g): g is string => !!g && g.length > 1);

  return Array.from(new Set(genera));
}

async function fetchLiterature(speciesName: string): Promise<LiteratureResult> {
  const response = await fetch(
    `/api/literature?species=${encodeURIComponent(speciesName)}`,
    { headers: { Accept: "application/json" } },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch literature for ${speciesName}: ${response.status}`,
    );
  }

  const data: ApiPayload = await response.json();
  const genera = generaOf([
    data.acceptedName,
    data.genus,
    ...data.synonymsSearched,
  ]);

  const species = data.species.map((w) => toResult(w, genera));
  const genusRelated =
    data.genusRelated?.map((w) => toResult(w, genera)) ?? null;

  return {
    acceptedName: data.acceptedName,
    genus: data.genus,
    synonymsSearched: data.synonymsSearched,
    species: groupByYear(species),
    speciesCount: species.length,
    genusRelated: genusRelated ? groupByYear(genusRelated) : null,
    genusRelatedCount: genusRelated?.length ?? 0,
    minSpeciesResults: data.minSpeciesResults,
    partial: data.partial,
    fromYear: data.fromYear ?? null,
  };
}

export type HigherTaxonRank = "order" | "family" | "genus";

export interface HigherTaxonLiteratureResult {
  name: string;
  rank: HigherTaxonRank;
  works: PublicationsByYear;
  count: number;
  /** True when some CrossRef requests failed, so the list may be incomplete. */
  partial: boolean;
  /** The earliest publication year searched; null when every year is. */
  fromYear: number | null;
}

interface HigherTaxonApiPayload {
  name: string;
  rank: HigherTaxonRank;
  /** The family searched beside a genus; null for an order or family. */
  context: string | null;
  works: ApiWork[];
  partial: boolean;
  fromYear: number | null;
}

/**
 * Publications naming an order, family or genus, from the backend's
 * `/{rank}/{name}/literature`. One name, no synonyms: unlike a species, a
 * higher taxon is rarely short of literature.
 *
 * A genus is searched beside its `family` when one is given, because many
 * genus names are words in other fields too.
 */
async function fetchHigherTaxonLiterature(
  rank: HigherTaxonRank,
  name: string,
  family?: string | null,
): Promise<HigherTaxonLiteratureResult> {
  const params = new URLSearchParams({ rank, name });

  if (rank === "genus" && family) params.set("family", family);

  const response = await fetch(`/api/higher-taxon-literature?${params}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch literature for ${rank} ${name}: ${response.status}`,
    );
  }

  const data: HigherTaxonApiPayload = await response.json();
  // Sentence-casing a title would otherwise lower-case the taxon itself, and
  // the "(Lepidoptera: Nymphalidae)" most titles carry.
  const names = [data.name, data.context, ORDER_NAME].filter(
    (n): n is string => !!n,
  );
  const works = data.works.map((w) => toResult(w, names));

  return {
    name: data.name,
    rank: data.rank,
    works: groupByYear(works),
    count: works.length,
    partial: data.partial,
    fromYear: data.fromYear ?? null,
  };
}

export { fetchHigherTaxonLiterature, fetchLiterature };
