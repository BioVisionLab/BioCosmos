"use client";

import React, {
  useState,
  useEffect,
  useLayoutEffect,
  useRef,
  useSyncExternalStore,
  Suspense,
} from "react";
import { useRouter } from "next/navigation";
import { ImageLoading } from "@/components/Loadings";
import {
  searchSemantic,
  SearchExpiredError,
  SemanticSearchResult,
} from "@/lib/ml_search";
import {
  getCachedSearch,
  saveSearchScroll,
  setCachedSearch,
} from "@/lib/semanticSearchCache";
import { MLSearchResultCard } from "./MlResultCard";
import SearchForm from "@/components/SearchForm";
import { FlaskConical } from "lucide-react";
import {
  SemanticSearchDescription,
  SemanticSearchLegend,
} from "@/components/SemanticSearchFunctions";
import Tips from "@/components/Tips";
import BackLink from "@/components/BackLink";

function errorMessage(err: unknown): string {
  return err instanceof Error && err.message
    ? err.message
    : "An unexpected error occurred";
}

/** Append `next` to `current`, skipping species already shown. */
function appendUnique(
  current: SemanticSearchResult[],
  next: SemanticSearchResult[],
): SemanticSearchResult[] {
  const seen = new Set(current.map((item) => item.species));
  return [...current, ...next.filter((item) => !seen.has(item.species))];
}

const subscribeNever = () => () => {};

/**
 * The cache lives in the browser, so the server render (and the hydration
 * pass that must match it) can't see it. Mount the stateful view only once
 * hydrated; client-side navigations, such as Back from a species page, are
 * already hydrated and render the cached grid on their first paint.
 */
function SemanticSearchResults({ query }: { query: string }) {
  const hydrated = useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );
  if (!hydrated) {
    return (
      <div className="flex flex-col items-center mt-24">
        <ImageLoading size={240} msg="Loading results" />
      </div>
    );
  }
  return <SemanticSearchView query={query} />;
}

function SemanticSearchView({ query }: { query: string }) {
  // Start from the cached search when returning from a species page, so the
  // grid, its extra pages and the scroll position come back without a request.
  const [cached] = useState(() => getCachedSearch(query));
  const [results, setResults] = useState<SemanticSearchResult[]>(
    cached?.results ?? [],
  );
  const [total, setTotal] = useState(cached?.total ?? 0);
  const [searchId, setSearchId] = useState<string | null>(
    cached?.searchId ?? null,
  );
  const [hasMore, setHasMore] = useState(cached?.hasMore ?? false);
  const [loading, setLoading] = useState(cached === null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  const [attempt, setAttempt] = useState(0);
  const loadMoreController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!query) return;
    // A cached search is only replaced by an explicit re-search.
    if (cached && attempt === 0) return;

    // Abort the previous search so a slow, stale response cannot overwrite
    // the results of a newer query.
    const controller = new AbortController();

    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      setMoreError(null);
      try {
        const page = await searchSemantic(query, {
          refresh: attempt > 0,
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setResults(page.results);
        setTotal(page.total);
        setSearchId(page.searchId);
        setHasMore(page.hasMore);
        setCachedSearch(query, {
          searchId: page.searchId,
          results: page.results,
          total: page.total,
          hasMore: page.hasMore,
          scrollY: 0,
        });
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        setResults([]);
        setHasMore(false);
        setError(errorMessage(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchResults();
    return () => controller.abort();
  }, [query, attempt, cached]);

  // Restore the scroll position once the cached grid has rendered.
  useLayoutEffect(() => {
    if (cached && cached.scrollY > 0) window.scrollTo(0, cached.scrollY);
  }, [cached]);

  // Remember where the reader was, whichever way they leave the page. The
  // unmount save is a layout cleanup so it runs before the next route
  // scrolls the window back to the top.
  useLayoutEffect(() => {
    const save = () => saveSearchScroll(query, window.scrollY);
    window.addEventListener("pagehide", save);
    return () => {
      save();
      window.removeEventListener("pagehide", save);
    };
  }, [query]);

  useEffect(() => () => loadMoreController.current?.abort(), []);

  const loadMore = async () => {
    if (loadingMore) return;
    loadMoreController.current?.abort();
    const controller = new AbortController();
    loadMoreController.current = controller;

    setLoadingMore(true);
    setMoreError(null);
    const offset = results.length;
    try {
      let page;
      try {
        page = await searchSemantic(query, {
          searchId,
          offset,
          signal: controller.signal,
        });
      } catch (err: unknown) {
        // The backend dropped the cached search: run it again and continue
        // from the same position, keeping what is already on screen.
        if (!(err instanceof SearchExpiredError)) throw err;
        page = await searchSemantic(query, {
          offset,
          refresh: true,
          signal: controller.signal,
        });
      }
      if (controller.signal.aborted) return;
      const merged = appendUnique(results, page.results);
      setResults(merged);
      setTotal(page.total);
      setSearchId(page.searchId);
      setHasMore(page.hasMore);
      setCachedSearch(query, {
        searchId: page.searchId,
        results: merged,
        total: page.total,
        hasMore: page.hasMore,
      });
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setMoreError(errorMessage(err));
    } finally {
      if (!controller.signal.aborted) setLoadingMore(false);
    }
  };

  const router = useRouter();

  const handleSearch = (newQuery: string, mode: string) => {
    if (!newQuery.trim()) return;
    setError(null);
    setMoreError(null);
    setLoading(true);
    setResults([]);
    setHasMore(false);

    if (newQuery === query) {
      setAttempt((previous) => previous + 1);
      return;
    }

    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}`;
    router.push(newUrl);
  };

  return (
    <div className="items-center max-w-7xl w-full mx-auto">
      <BackLink />
      <div id="search-query" className="mb-8 mt-8 text-center space-y-4">
        <SemanticSearchDescription />
        <SearchForm
          mode="semantic"
          icon={FlaskConical}
          onSubmit={handleSearch}
          query={query}
          placeholder="Orange butterfly with black lines"
        />
      </div>
      <div id="results-section" className="mt-2">
        <div className="mb-6 text-center">
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-linear-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        {error ? (
          <p className="text-center text-burnt-peach-500">Error: {error}</p>
        ) : (
          <MlSearchResults
            results={results}
            total={total}
            query={query}
            loading={loading}
            hasMore={hasMore}
            loadingMore={loadingMore}
            moreError={moreError}
            onLoadMore={loadMore}
          />
        )}
      </div>
    </div>
  );
}

function MlSearchResults({
  results,
  total,
  query,
  loading,
  hasMore,
  loadingMore,
  moreError,
  onLoadMore,
}: {
  results: SemanticSearchResult[];
  total: number;
  query: string;
  loading: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  moreError: string | null;
  onLoadMore: () => void;
}) {
  if (query.trim() === "" && !loading) {
    return <p>Please enter a search query.</p>;
  }

  if (results.length === 0 && !loading) {
    return (
      <p>
        No results found for &quot;{query}&quot;. Please try a different query.
      </p>
    );
  }

  return (
    <>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="mt-8">
          <SemanticSearchLegend />
          <div className="mb-4 mt-8">
            <h2 className="text-lg wrap-break-word text-deep-mocha-700 dark:text-deep-mocha-200">
              {results.length < total
                ? `Showing ${results.length} of ${total} results`
                : `Found ${total} ${total === 1 ? "result" : "results"}`}{" "}
              for &quot;{query}&quot;
            </h2>
            <Tips message="Click on an image to view species page" />
          </div>
          <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(min(100%,140px),1fr))] gap-3 sm:gap-4">
            {results.map((item) => (
              <Suspense
                key={item.imgId}
                fallback={<div>Loading species...</div>}
              >
                <MLSearchResultCard data={item} toolNames={item.tool_names} />
              </Suspense>
            ))}
          </div>
          {(hasMore || moreError) && (
            <div className="mt-8 flex flex-col items-center gap-2">
              {moreError && (
                <p className="text-sm text-burnt-peach-500">
                  Could not load more results: {moreError}
                </p>
              )}
              <button
                type="button"
                onClick={onLoadMore}
                disabled={loadingMore}
                aria-busy={loadingMore}
                className="rounded-lg bg-gradient-to-br from-hunter-green-500/50 to-pacific-blue-700/50 px-6 py-2 text-deep-mocha-100 transition hover:bg-pacific-blue-600/70 disabled:cursor-wait disabled:opacity-60"
              >
                {loadingMore ? "Loading…" : moreError ? "Retry" : "Show more"}
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default SemanticSearchResults;
