import type { SemanticSearchResult } from "@/lib/ml_search";

/**
 * Client-side cache of semantic search results, so returning from a species
 * page restores the grid (and every "Show more" page) without a request.
 *
 * A module-level map survives client-side navigation; sessionStorage mirrors
 * it so a reload or a full Back navigation is covered too. Entries live as
 * long as the backend keeps the search they page through.
 */
export interface CachedSemanticSearch {
  searchId: string | null;
  results: SemanticSearchResult[];
  total: number;
  hasMore: boolean;
  scrollY: number;
  savedAt: number;
}

const TTL_MS = 15 * 60 * 1000;
const MAX_ENTRIES = 10;
const STORAGE_PREFIX = "semantic-search:";

const memory = new Map<string, CachedSemanticSearch>();

function cacheKey(query: string): string {
  return query.trim().toLowerCase().replace(/\s+/g, " ");
}

function isFresh(entry: CachedSemanticSearch): boolean {
  return Date.now() - entry.savedAt <= TTL_MS;
}

function readStorage(key: string): CachedSemanticSearch | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_PREFIX + key);
    if (!raw) return null;
    const entry = JSON.parse(raw) as CachedSemanticSearch;
    return Array.isArray(entry?.results) ? entry : null;
  } catch {
    return null;
  }
}

function writeStorage(key: string, entry: CachedSemanticSearch | null) {
  try {
    if (entry) {
      window.sessionStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(entry));
    } else {
      window.sessionStorage.removeItem(STORAGE_PREFIX + key);
    }
  } catch {
    // Storage may be full or blocked; the in-memory copy still works.
  }
}

function getCachedSearch(query: string): CachedSemanticSearch | null {
  if (typeof window === "undefined") return null;
  const key = cacheKey(query);
  const entry = memory.get(key) ?? readStorage(key);
  if (!entry) return null;
  if (!isFresh(entry)) {
    memory.delete(key);
    writeStorage(key, null);
    return null;
  }
  memory.set(key, entry);
  return entry;
}

function setCachedSearch(
  query: string,
  entry: Omit<CachedSemanticSearch, "savedAt" | "scrollY"> & {
    scrollY?: number;
  },
) {
  if (typeof window === "undefined") return;
  const key = cacheKey(query);
  const previous = memory.get(key);
  const next: CachedSemanticSearch = {
    ...entry,
    scrollY: entry.scrollY ?? previous?.scrollY ?? 0,
    savedAt: previous?.searchId === entry.searchId ? previous.savedAt : Date.now(),
  };
  memory.delete(key);
  memory.set(key, next);
  while (memory.size > MAX_ENTRIES) {
    const oldest = memory.keys().next().value;
    if (oldest === undefined) break;
    memory.delete(oldest);
  }
  writeStorage(key, next);
}

function saveSearchScroll(query: string, scrollY: number) {
  const entry = getCachedSearch(query);
  if (entry) setCachedSearch(query, { ...entry, scrollY });
}

export { getCachedSearch, setCachedSearch, saveSearchScroll };
