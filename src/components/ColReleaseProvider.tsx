"use client";

import { createContext, useContext, type ReactNode } from "react";

import { COL_RELEASE } from "@/lib/colTaxonomy";

const ColReleaseContext = createContext<string>(COL_RELEASE);

/**
 * Hands the ingested Catalogue of Life release to every attribution.
 *
 * The root layout fetches the label on the server and wraps the whole site in
 * this, so server and client components alike read the same release without
 * a request of their own.
 */
export function ColReleaseProvider({
  release,
  children,
}: {
  release: string | null;
  children: ReactNode;
}) {
  return (
    <ColReleaseContext value={release ?? COL_RELEASE}>
      {children}
    </ColReleaseContext>
  );
}

/** The ingested release's label, or `COL_RELEASE` when it is unknown. */
export function useColRelease(): string {
  return useContext(ColReleaseContext);
}

/**
 * The release label as text, usable from a server component.
 *
 * @param release An explicit label; the ingested one when omitted.
 */
export function ColReleaseLabel({ release }: { release?: string }) {
  const ingested = useColRelease();

  return <>{release ?? ingested}</>;
}
