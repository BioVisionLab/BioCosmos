"use client";

import { ErrorState } from "@/components/ErrorState";

/**
 * Scoped to the species route so a failure in one panel — the visually
 * similar species search is the slowest and most failure-prone of them —
 * does not take the site chrome down with it.
 */
export default function SpeciesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      error={error}
      reset={reset}
      title="This species page could not be loaded"
      description="One of the panels on this page failed. Try again, or open the species from the collection listing."
    />
  );
}
