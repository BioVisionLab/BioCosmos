"use client";

import { useEffect, useState } from "react";

import MorphospacePlot from "@/components/morphospace/MorphospacePlot";
import DisparityPanel from "@/components/morphospace/DisparityPanel";
import {
  fetchScopeMorphospace,
  type MorphospaceRank,
  type ScopeMorphospace,
} from "@/lib/morphospace";
import { useInView } from "@/lib/useInView";

export function MorphospaceIntro() {
  return (
    <p className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300 mb-4">
      Variation in species coloration mapped onto the latent space. Each species
      is represented by two points, one for its dorsal side and one for its
      ventral side. The farther apart the dorsal and ventral points are, the
      more different the two sides are in coloration.
      <br />
    </p>
  );
}

interface Props {
  rank: MorphospaceRank;
  name: string;
  headingId: string;
}

/**
 * The morphospace section of a genus or family page.
 *
 * Fetched only when scrolled near, and rendered not at all when the scope has
 * no morphospace (too few species, or the tables not yet integrated), so a
 * page without one looks exactly as it did before.
 */
export default function MorphospaceSection({ rank, name, headingId }: Props) {
  const { ref, inView: near } = useInView<HTMLElement>("400px");
  const [data, setData] = useState<ScopeMorphospace | null | undefined>(
    undefined,
  );

  useEffect(() => {
    if (!near) return;
    let cancelled = false;
    fetchScopeMorphospace(rank, name)
      .then((result) => !cancelled && setData(result))
      .catch(() => !cancelled && setData(null));
    return () => {
      cancelled = true;
    };
  }, [near, rank, name]);

  if (data === null) return null;

  return (
    <section ref={ref} className="mb-10" aria-labelledby={headingId}>
      <h2 id={headingId} className="text-2xl font-semibold mb-3">
        Morphospace
      </h2>
      <MorphospaceIntro />
      {data === undefined ? (
        <div className="h-110 rounded-xl border border-deep-mocha-100 dark:border-deep-mocha-800 animate-pulse" />
      ) : (
        <div className="space-y-6">
          <div className="p-4 border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl bg-white dark:bg-deep-mocha-950">
            <MorphospacePlot data={data} />
          </div>
          <DisparityPanel data={data} />
        </div>
      )}
    </section>
  );
}
