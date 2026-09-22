"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * The recovery UI behind every `error.tsx` in the app.
 *
 * Until this existed a throw anywhere in a client subtree — a thumbnail
 * handler, a panel that got a shape it did not expect — unmounted the whole
 * tree to a blank page, and the only way back was for the reader to reload by
 * hand. That is what "it renders partially, a refresh fixes it" was.
 *
 * `reset()` re-renders the failed segment without a full navigation, so a
 * transient backend failure costs a click rather than a page load.
 */
export function ErrorState({
  error,
  reset,
  title = "Something went wrong",
  description,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  title?: string;
  description?: string;
}) {
  useEffect(() => {
    // The digest is the only handle on a server-side throw, whose message is
    // redacted in production.
    console.error("Route error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
      <h2 className="text-2xl font-semibold text-burnt-peach-600 dark:text-burnt-peach-400">
        {title}
      </h2>
      <p className="mt-3 max-w-md text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        {description ??
          "This section failed to load. Trying again often resolves it — the backend may still be starting up."}
      </p>
      {error.digest ? (
        <p className="mt-2 font-mono text-xs text-deep-mocha-500 dark:text-deep-mocha-500">
          Reference: {error.digest}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-full bg-pacific-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-pacific-blue-700"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-full border border-deep-mocha-300 px-5 py-2 text-sm font-medium text-deep-mocha-700 transition-colors hover:bg-deep-mocha-200/60 dark:border-deep-mocha-600 dark:text-deep-mocha-300 dark:hover:bg-deep-mocha-800/60"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
