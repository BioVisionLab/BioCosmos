import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import { ColAttribution } from "@/components/Attribution";
import HigherTaxonHeader from "@/components/HigherTaxonHeader";
import TaxonBreadcrumb, { type Crumb } from "@/components/TaxonBreadcrumb";
import TaxonImageStrip from "@/components/TaxonImageStrip";
import TaxonomyTree, { UnrecordedTaxaNote } from "@/components/TaxonomyTree";
import TaxonomyTreeControls from "@/components/TaxonomyTreeControls";
import {
  REPRESENTATIVE_IMAGE_LIMIT,
  fetchHigherTaxon,
  pickRepresentatives,
} from "@/lib/higherTaxa";
import { familyHref, genusHref, isCanonicalTaxonSlug } from "@/lib/taxonSlug";

// See the note on the family page: the thirty-day cache is on the fetch, not
// on this segment, and this flag does not defeat it.
export const dynamic = "force-dynamic";

const TREE_ID = "genus-classification-tree";

interface GenusPageProps {
  params: Promise<{ genusName: string }>;
}

export async function generateMetadata({
  params,
}: GenusPageProps): Promise<Metadata> {
  const { genusName } = await params;
  const taxon = await fetchHigherTaxon("genus", decodeURIComponent(genusName));
  if (!taxon) return { title: "Genus not found" };
  return {
    title: `${taxon.name} — genus`,
    description:
      `${taxon.counts.speciesCount.toLocaleString()} species and ` +
      `${taxon.counts.imageCount.toLocaleString()} specimen images in the ` +
      `butterfly genus ${taxon.name}.`,
    alternates: { canonical: genusHref(taxon.name) },
  };
}

export default async function GenusPage({ params }: GenusPageProps) {
  const { genusName } = await params;
  const raw = decodeURIComponent(genusName);

  // Deliberately no `loading.tsx` beside this file. A loading boundary puts
  // the page inside Suspense, so Next flushes a 200 shell before this
  // function runs — which turns `notFound()` into a soft 404 and demotes the
  // redirect below to a client-side hop. Correct status codes are worth more
  // than a skeleton on a response that takes a few hundred milliseconds.
  if (!isCanonicalTaxonSlug(raw)) permanentRedirect(genusHref(raw));

  const taxon = await fetchHigherTaxon("genus", raw);
  if (!taxon) notFound();

  // The family is the one crumb this page cannot know from its own URL. It
  // comes from the classification, which is why the stub that preceded this
  // had a literal "Family Name" standing in its place.
  const family = taxon.classification?.family;
  const crumbs: Crumb[] = [{ label: "Home", href: "/" }];
  if (family) crumbs.push({ label: family, href: familyHref(family) });
  crumbs.push({ label: taxon.name, italic: true });

  return (
    <section className="m-2">
      <TaxonBreadcrumb items={crumbs} />
      <HigherTaxonHeader taxon={taxon} />

      <section className="mb-10" aria-labelledby="genus-images">
        <h2 id="genus-images" className="text-2xl font-semibold mb-3">
          Species in this genus
        </h2>
        <TaxonImageStrip
          images={pickRepresentatives(taxon.images, REPRESENTATIVE_IMAGE_LIMIT)}
        />
      </section>

      <section
        aria-labelledby="genus-tree"
        className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg"
      >
        <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl flex flex-wrap items-center justify-between gap-3">
          <h2 id="genus-tree" className="text-2xl font-semibold">
            Classification
          </h2>
          <TaxonomyTreeControls treeId={TREE_ID} label="Filter species" />
        </div>
        <div className="p-4">
          <TaxonomyTree
            id={TREE_ID}
            nodes={taxon.tree}
            bottomRank="species"
            highlightRank="genus"
            nodeCount={taxon.nodeCount}
          />
          <UnrecordedTaxaNote taxa="species" />
          <ColAttribution />
        </div>
      </section>
    </section>
  );
}
