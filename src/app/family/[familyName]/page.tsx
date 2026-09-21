import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import { ColAttribution } from "@/components/Attribution";
import HigherTaxonHeader from "@/components/HigherTaxonHeader";
import TaxonBreadcrumb from "@/components/TaxonBreadcrumb";
import TaxonImageStrip from "@/components/TaxonImageStrip";
import TaxonomyTree from "@/components/TaxonomyTree";
import TaxonomyTreeControls from "@/components/TaxonomyTreeControls";
import {
  REPRESENTATIVE_IMAGE_LIMIT,
  fetchHigherTaxon,
  pickRepresentatives,
} from "@/lib/higherTaxa";
import { familyHref, isCanonicalTaxonSlug } from "@/lib/taxonSlug";

// Never pre-rendered at build time: API_HOST is unavailable during the Docker
// build. This does not defeat the thirty-day cache — that lives on the fetch
// in @/lib/higherTaxa, which is explicit about its lifetime and so survives
// the no-store default this flag sets. See the note there before adding
// `fetchCache` to this segment.
export const dynamic = "force-dynamic";

const TREE_ID = "family-classification-tree";

interface FamilyPageProps {
  params: Promise<{ familyName: string }>;
}

export async function generateMetadata({
  params,
}: FamilyPageProps): Promise<Metadata> {
  const { familyName } = await params;
  const taxon = await fetchHigherTaxon("family", decodeURIComponent(familyName));
  if (!taxon) return { title: "Family not found" };
  return {
    title: `${taxon.name} — family`,
    description:
      `${taxon.counts.genusCount?.toLocaleString() ?? "—"} genera, ` +
      `${taxon.counts.speciesCount.toLocaleString()} species and ` +
      `${taxon.counts.imageCount.toLocaleString()} specimen images in the ` +
      `butterfly family ${taxon.name}.`,
    alternates: { canonical: familyHref(taxon.name) },
  };
}

export default async function FamilyPage({ params }: FamilyPageProps) {
  const { familyName } = await params;
  const raw = decodeURIComponent(familyName);

  // The species page linked here with Catalogue of Life's own capitalisation
  // for a long time. One taxon, one URL: redirect rather than serve the page
  // at both and split every cache key in two.
  // Deliberately no `loading.tsx` beside this file. A loading boundary puts
  // the page inside Suspense, so Next flushes a 200 shell before this
  // function runs — which turns `notFound()` into a soft 404 and demotes the
  // redirect below to a client-side hop. Correct status codes are worth more
  // than a skeleton on a response that takes a few hundred milliseconds.
  if (!isCanonicalTaxonSlug(raw)) permanentRedirect(familyHref(raw));

  const taxon = await fetchHigherTaxon("family", raw);
  if (!taxon) notFound();

  return (
    <section className="m-2">
      <TaxonBreadcrumb
        items={[{ label: "Home", href: "/" }, { label: taxon.name }]}
      />
      <HigherTaxonHeader taxon={taxon} />

      <section className="mb-10" aria-labelledby="family-images">
        <h2 id="family-images" className="text-2xl font-semibold mb-3">
          Species in this family
        </h2>
        <TaxonImageStrip
          images={pickRepresentatives(taxon.images, REPRESENTATIVE_IMAGE_LIMIT)}
        />
      </section>

      <section
        aria-labelledby="family-tree"
        className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg"
      >
        <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl flex flex-wrap items-center justify-between gap-3">
          <h2 id="family-tree" className="text-2xl font-semibold">
            Classification
          </h2>
          <TaxonomyTreeControls treeId={TREE_ID} label="Filter genera" />
        </div>
        <div className="p-4">
          <TaxonomyTree
            id={TREE_ID}
            nodes={taxon.tree}
            bottomRank="genus"
            nodeCount={taxon.nodeCount}
          />
          <ColAttribution />
        </div>
      </section>
    </section>
  );
}
