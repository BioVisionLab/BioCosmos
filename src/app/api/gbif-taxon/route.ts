import { NextResponse } from "next/server";

import { cleanSpeciesName } from "@/lib/names";

const GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match";
const GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search";
const CACHE_TTL_MS = 1000 * 60 * 60 * 24; // 24 hours
const CACHE_MAX_ENTRIES = 500;

/**
 * Ranks a distribution may be drawn from.
 *
 * A HIGHERRANK match resolves to the genus, whose occurrences would paint the
 * whole genus's range on a page about one species. Better to report that the
 * name was not matched.
 */
const MAPPABLE_RANKS = new Set(["SPECIES", "SUBSPECIES", "VARIETY", "FORM"]);

interface CacheEntry<T> {
  value: T;
  timestamp: number;
}

/**
 * A small bounded TTL cache.
 *
 * Bounded because the previous unbounded Map grew by one entry per species
 * ever viewed and was never evicted. Map preserves insertion order, so the
 * oldest key is simply the first.
 */
class TtlCache<T> {
  private entries = new Map<string, CacheEntry<T>>();

  get(key: string): T | undefined {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (Date.now() - entry.timestamp >= CACHE_TTL_MS) {
      this.entries.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T): void {
    this.entries.delete(key);
    this.entries.set(key, { value, timestamp: Date.now() });
    while (this.entries.size > CACHE_MAX_ENTRIES) {
      const oldest = this.entries.keys().next();
      if (oldest.done) break;
      this.entries.delete(oldest.value);
    }
  }
}

// Negative matches are cached too: a name GBIF does not know would otherwise
// be looked up again every time the map mounts.
const matchCache = new TtlCache<number | null>();
const countCache = new TtlCache<number>();

interface GbifMatch {
  usageKey?: number;
  /** Set only when the match is a synonym; this is the current taxon. */
  acceptedUsageKey?: number;
  scientificName?: string;
  matchType?: string;
  status?: string;
  rank?: string;
  confidence?: number;
}

/**
 * Resolve a name to a GBIF backbone key, or null when GBIF does not have it.
 *
 * Matching first is what makes the map work at all for a renamed taxon: the
 * occurrence endpoint's `scientificName` filter is a literal backbone lookup,
 * whereas `species/match` resolves a synonym to its accepted usage, and
 * querying by the resulting `taxonKey` then includes subspecies records too.
 */
async function matchTaxon(name: string): Promise<number | null> {
  const cacheKey = name.toLowerCase();
  const cached = matchCache.get(cacheKey);
  if (cached !== undefined) return cached;

  const response = await fetch(
    `${GBIF_MATCH_URL}?name=${encodeURIComponent(name)}&strict=false`,
    { method: "GET", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`GBIF match failed: ${response.status} ${response.statusText}`);
  }

  const match: GbifMatch = await response.json();
  const usable =
    match.matchType &&
    match.matchType !== "NONE" &&
    MAPPABLE_RANKS.has((match.rank ?? "").toUpperCase());

  // `usageKey` is the key of the name that matched, which for a synonym is
  // the synonym itself — and almost nothing is filed under a synonym. GBIF
  // holds 4 georeferenced records under Danaus archippus and 810k under the
  // accepted Danaus plexippus, so taking the wrong one here would leave the
  // map as empty as the bug this replaces.
  const key = usable
    ? (match.acceptedUsageKey ?? match.usageKey ?? null)
    : null;
  matchCache.set(cacheKey, key ?? null);
  return key ?? null;
}

/**
 * How many georeferenced, issue-free records GBIF holds for the taxon.
 *
 * The map draws those records as density tiles straight from the GBIF Maps
 * API, so the only thing fetched here is the total for the legend: `limit=0`
 * returns the count without a single record.
 */
async function countOccurrences(taxonKey: number): Promise<number> {
  const cacheKey = String(taxonKey);
  const cached = countCache.get(cacheKey);
  if (cached !== undefined) return cached;

  const response = await fetch(
    `${GBIF_OCCURRENCE_URL}?taxonKey=${taxonKey}&limit=0` +
      `&hasCoordinate=true&hasGeospatialIssue=false`,
    { method: "GET", headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(
      `GBIF occurrence count failed: ${response.status} ${response.statusText}`,
    );
  }

  const data = await response.json();
  const count = typeof data.count === "number" ? data.count : 0;
  countCache.set(cacheKey, count);
  return count;
}

/**
 * Turn whatever the page holds into a name GBIF can match.
 *
 * The species page keys on a URL slug, so this receives `danaus_plexippus`
 * rather than `Danaus plexippus`.
 */
function candidateNames(recorded: string, accepted: string | null): string[] {
  const names = [accepted, recorded]
    .filter((name): name is string => !!name && !!name.trim())
    .map((name) => cleanSpeciesName(name).trim())
    // A single word is a genus, which is not a distribution for a species.
    .filter((name) => name.includes(" "));
  return Array.from(new Set(names));
}

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const species = searchParams.get("species");
  const accepted = searchParams.get("accepted");

  if (!species) {
    return NextResponse.json(
      { error: "Query parameter 'species' is required", status: "error" },
      { status: 400 },
    );
  }

  const candidates = candidateNames(species, accepted);
  if (candidates.length === 0) {
    return NextResponse.json({ status: "unmatched" });
  }

  try {
    // The accepted name is tried first, then the recorded one. GBIF resolves
    // a synonym to the same accepted key, so the two usually converge; the
    // second pass is for names only the collection uses.
    for (const name of candidates) {
      const taxonKey = await matchTaxon(name);
      if (taxonKey === null) continue;
      const count = await countOccurrences(taxonKey);
      return NextResponse.json({
        status: "ok",
        matchedName: name,
        taxonKey,
        count,
      });
    }

    console.info(`No GBIF backbone match for: ${candidates.join(" / ")}`);
    return NextResponse.json({ status: "unmatched" });
  } catch (error) {
    console.error(`Error resolving GBIF taxon for ${species}:`, error);
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    return NextResponse.json(
      { status: "error", error: message },
      { status: 502 },
    );
  }
}
