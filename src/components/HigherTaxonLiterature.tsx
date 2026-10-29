"use client";

import { useEffect, useState } from "react";

import {
  LITERATURE_PAGE_SIZE,
  PagedPublications,
  PartialNotice,
} from "@/app/species/[speciesName]/components/LiteraturePage";
import { CrossRefAttribution, CrossRefLink } from "@/components/Attribution";
import Info from "@/components/Info";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  type HigherTaxonLiteratureResult,
  type HigherTaxonRank,
  fetchHigherTaxonLiterature,
} from "@/lib/crossref";

/**
 * Publications naming an order, family or genus.
 *
 * Fetched on mount, and mounted only when the tab is first opened, so a page
 * view that never opens it never calls CrossRef. `onCount` hands the total
 * back to the tab label.
 */
export default function HigherTaxonLiterature({
  rank,
  name,
  family,
  onCount,
}: {
  rank: HigherTaxonRank;
  name: string;
  /** Searched beside a genus to keep out namesakes in other fields. */
  family?: string | null;
  onCount?: (count: number) => void;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "failed" }
    | { status: "loaded"; literature: HigherTaxonLiteratureResult }
  >({ status: "loading" });
  const [limit, setLimit] = useState(LITERATURE_PAGE_SIZE);

  useEffect(() => {
    let isMounted = true;

    fetchHigherTaxonLiterature(rank, name, family)
      .then((literature) => {
        if (!isMounted) return;

        setState({ status: "loaded", literature });
        onCount?.(literature.count);
      })
      .catch((error) => {
        console.error("Error fetching literature data:", error);

        if (isMounted) setState({ status: "failed" });
      });

    return () => {
      isMounted = false;
    };
  }, [rank, name, family, onCount]);

  if (state.status === "loading") {
    return <TextLoading msg="Loading literature" />;
  }

  if (state.status === "failed") {
    return (
      <NoData text="Literature could not be loaded right now. Please try again later." />
    );
  }

  const { literature } = state;
  const since = literature.fromYear ? ` since ${literature.fromYear}` : "";
  const italic = rank === "genus";
  const taxon = italic ? <em>{literature.name}</em> : literature.name;

  if (literature.count === 0) {
    return (
      <div>
        <NoData text={`No publications on ${literature.name} found${since}.`} />
        {literature.partial ? <PartialNotice /> : null}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Info>
          <p>
            Fetched automatically from <CrossRefLink /> and kept only when the
            title or abstract names {taxon}
            {since}. It may still contain irrelevant publications.
          </p>
        </Info>
        {literature.partial ? <PartialNotice /> : null}
      </div>

      {/* The total is on the card's summary line, above. */}
      <PagedPublications
        publications={literature.works}
        section="taxon"
        limit={limit}
        onLimit={setLimit}
      />

      <CrossRefAttribution isLarge={true} />
    </div>
  );
}
