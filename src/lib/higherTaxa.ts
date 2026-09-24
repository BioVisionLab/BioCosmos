/**
 * Data for the order, family and genus pages.
 *
 * Server-only: `API_HOST` is not a `NEXT_PUBLIC_` variable, so this module is
 * imported by server components and never reaches the browser. Nothing on
 * these pages needs the data on the client — the tree is fully known at
 * render time — so there is no `/api/family/*` proxy route to go with it.
 */

import { cache } from "react";

import { API_HOST } from "@/lib/config";
import {
  normalizeColTaxonomy,
  type ColRank,
  type ColTaxonomy,
} from "@/lib/colTaxonomy";
import { speciesHref, toTaxonSlug } from "@/lib/taxonSlug";

export type HigherRank = "order" | "family" | "genus";

/**
 * Thirty days.
 *
 * A family's composition changes only when Catalogue of Life cuts a release
 * and the backend re-ingests it, which is far rarer than a page view. The
 * backend sends the same lifetime and an ETag keyed on that ingestion, so a
 * shared cache can notice sooner than thirty days when one happens.
 */
export const HIGHER_TAXON_REVALIDATE = 60 * 60 * 24 * 30;

/** How many tiles the representative image strip holds. */
export const REPRESENTATIVE_IMAGE_LIMIT = 20;

export interface TaxonNode {
  key: string;
  /** The accepted name, which is what the reader should see. */
  name: string;
  /**
   * Present only when the collection records this taxon under a different
   * name than Catalogue of Life accepts. Two species can then display the
   * same accepted name, and this is what tells them apart.
   */
  recordedName: string | null;
  rank: ColRank | "unplaced";
  authorship: string | null;
  /** Only the ranks that have a page of their own carry one. */
  href: string | null;
  colLink: string | null;
  /** Families with images below this node; set only on an order's tree. */
  familyCount: number | null;
  genusCount: number | null;
  speciesCount: number;
  imageCount: number;
  /** False for a genus Catalogue of Life cannot place inside this family. */
  placed: boolean;
  /** One image to stand for the node; set only on an order's families. */
  imageId: string | null;
  /** The species that image shows. */
  imageName: string | null;
  children: TaxonNode[];
}

export interface RepresentativeImage {
  imageId: string;
  /** The recorded key, which is what the species route resolves on. */
  species: string;
  displayName: string;
}

export interface HigherTaxon {
  key: string;
  name: string;
  rank: HigherRank;
  /** The full lineage, for the header and the breadcrumb. */
  classification: ColTaxonomy | null;
  counts: {
    /** Families the collection has images of; set only on an order. */
    familyCount: number | null;
    genusCount: number | null;
    speciesCount: number;
    imageCount: number;
    /**
     * How many of each rank Catalogue of Life accepts inside the taxon, the
     * denominator for coverage. Null without the backbone, or beside a count
     * the page does not show.
     */
    familyTotal: number | null;
    genusTotal: number | null;
    speciesTotal: number | null;
  };
  tree: TaxonNode[];
  images: RepresentativeImage[];
  sources: { colTaxonomy: boolean; harmonizedTaxonomy: boolean };
  /** Every node in the tree, used to decide how much of it opens by default. */
  nodeCount: number;
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function optionalText(value: unknown): string | null {
  return text(value) || null;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function optionalCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeNode(raw: unknown): TaxonNode | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const key = text(source.key);
  const name = text(source.name);
  if (!key || !name) return null;

  const children = Array.isArray(source.children)
    ? source.children
        .map(normalizeNode)
        .filter((child): child is TaxonNode => child !== null)
    : [];

  return {
    key,
    name,
    recordedName: optionalText(source.recordedName),
    rank: (text(source.rank) || "unplaced") as TaxonNode["rank"],
    authorship: optionalText(source.authorship),
    href: optionalText(source.href),
    colLink: optionalText(source.colLink),
    familyCount: optionalCount(source.familyCount),
    genusCount: optionalCount(source.genusCount),
    speciesCount: count(source.speciesCount),
    imageCount: count(source.imageCount),
    placed: source.placed !== false,
    imageId: optionalText(source.imgId),
    imageName: optionalText(source.imgName),
    children,
  };
}

function normalizeImage(raw: unknown): RepresentativeImage | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const imageId = text(source.imgId);
  const species = text(source.species);
  if (!imageId || !species) return null;
  return {
    imageId,
    species,
    displayName: text(source.displayName) || species.replace(/_/g, " "),
  };
}

function countNodes(nodes: TaxonNode[]): number {
  return nodes.reduce(
    (total, node) => total + 1 + countNodes(node.children),
    0,
  );
}

/**
 * At most one image per species, so twenty tiles show twenty species rather
 * than twenty specimens of whichever one happens to be best photographed.
 *
 * The backend spreads them the same way. Doing it again here costs nothing
 * and means a regression there degrades a grid instead of misrepresenting how
 * varied a family is.
 */
export function pickRepresentatives(
  images: RepresentativeImage[],
  limit: number,
): RepresentativeImage[] {
  const seen = new Set<string>();
  const picked: RepresentativeImage[] = [];
  for (const image of images) {
    if (picked.length >= limit) break;
    // Keyed on where the tile leads, not on the raw record: two records that
    // resolve to the same species page would otherwise take two tiles and
    // show the reader the same name twice.
    const key = speciesHref(image.species);
    if (seen.has(key)) continue;
    seen.add(key);
    picked.push(image);
  }
  // Only reached when distinct species ran out before the grid did.
  for (const image of images) {
    if (picked.length >= limit) break;
    if (!picked.includes(image)) picked.push(image);
  }
  return picked;
}

/**
 * An order's families that have a page, most-photographed first: the order a
 * reader browsing by family is likeliest to want them in.
 */
export function familiesWithRecords(taxon: HigherTaxon): TaxonNode[] {
  const families: TaxonNode[] = [];
  const visit = (node: TaxonNode) => {
    if (node.rank === "family") {
      if (node.href) families.push(node);
      return;
    }
    node.children.forEach(visit);
  };
  taxon.tree.forEach(visit);
  return families.sort(
    (a, b) => b.imageCount - a.imageCount || a.name.localeCompare(b.name),
  );
}

function normalizeHigherTaxon(raw: unknown, rank: HigherRank): HigherTaxon | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const key = text(source.key);
  if (!key) return null;

  const counts = (source.counts ?? {}) as Record<string, unknown>;
  const sources = (source.sources ?? {}) as Record<string, unknown>;
  const tree = Array.isArray(source.tree)
    ? source.tree
        .map(normalizeNode)
        .filter((node): node is TaxonNode => node !== null)
    : [];

  return {
    key,
    name: text(source.name) || key,
    rank,
    classification: normalizeColTaxonomy(source.classification),
    counts: {
      familyCount: optionalCount(counts.familyCount),
      genusCount: optionalCount(counts.genusCount),
      speciesCount: count(counts.speciesCount),
      imageCount: count(counts.imageCount),
      familyTotal: optionalCount(counts.familyTotal),
      genusTotal: optionalCount(counts.genusTotal),
      speciesTotal: optionalCount(counts.speciesTotal),
    },
    tree,
    images: Array.isArray(source.images)
      ? source.images
          .map(normalizeImage)
          .filter((image): image is RepresentativeImage => image !== null)
      : [],
    sources: {
      colTaxonomy: sources.colTaxonomy === true,
      harmonizedTaxonomy: sources.harmonizedTaxonomy === true,
    },
    nodeCount: countNodes(tree),
  };
}

/**
 * Fetch one higher taxon, or null when there is no such taxon.
 *
 * Wrapped in `cache()` so the page body and `generateMetadata` share a single
 * call rather than each paying for one.
 *
 * The thirty-day lifetime sits on the fetch rather than on the route segment
 * because these pages carry `dynamic = "force-dynamic"` (API_HOST is
 * undefined during the Docker build). That flag sets a no-store *default*,
 * not a floor: Next only zeroes the revalidate when the fetch is itself
 * silent about caching, so an explicit value here survives. Do not add
 * `export const fetchCache` to those segments — "force-no-store" and
 * "only-no-store" are the one thing that would override this.
 */
export const fetchHigherTaxon = cache(
  async (rank: HigherRank, name: string): Promise<HigherTaxon | null> => {
    if (!API_HOST) return null;
    const slug = toTaxonSlug(name);
    if (!slug) return null;

    const response = await fetch(
      `${API_HOST}/${rank}/${encodeURIComponent(slug)}`,
      {
        headers: { Accept: "application/json" },
        next: {
          revalidate: HIGHER_TAXON_REVALIDATE,
          // Lets a post-release hook flush every higher-taxon page at once
          // with revalidateTag, instead of waiting out the thirty days.
          tags: ["higher-taxon", `higher-taxon:${rank}:${slug}`],
        },
      },
    );

    // A taxon that does not exist is a 404 page; a backend that is down is
    // not. Collapsing the two would tell a reader during an outage that a
    // family they are looking at does not exist.
    if (response.status === 404) return null;
    if (!response.ok) {
      throw new Error(
        `Failed to load ${rank} '${slug}': HTTP ${response.status}`,
      );
    }

    return normalizeHigherTaxon(await response.json(), rank);
  },
);
