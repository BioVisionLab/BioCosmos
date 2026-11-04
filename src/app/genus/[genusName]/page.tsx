import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import { ColAttribution } from "@/components/Attribution";
import HigherTaxonHeader from "@/components/HigherTaxonHeader";
import HigherTaxonTabs from "@/components/HigherTaxonTabs";
import MorphospaceSection from "@/components/morphospace/MorphospaceSection";
import TaxonBreadcrumb, { lineageCrumbs } from "@/components/TaxonBreadcrumb";
import TaxonSpeciesList, {
  parseSpeciesPage,
} from "@/components/TaxonSpeciesList";
import TaxonomyTree, { UnrecordedTaxaNote } from "@/components/TaxonomyTree";
import TaxonomyTreeControls from "@/components/TaxonomyTreeControls";
import { fetchHigherTaxon } from "@/lib/higherTaxa";
import { genusHref, isCanonicalTaxonSlug } from "@/lib/taxonSlug";

// See the note on the family page: the thirty-day cache is on the fetch, not
// on this segment, and this flag does not defeat it.
export const dynamic = "force-dynamic";

const TREE_ID = "genus-classification-tree";

interface GenusPageProps {
  params: Promise<{ genusName: string }>;
  searchParams: Promise<{ page?: string | string[] }>;
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

export default async function GenusPage({
  params,
  searchParams,
}: GenusPageProps) {
  const { genusName } = await params;
  const { page } = await searchParams;
  const raw = decodeURIComponent(genusName);

  // Deliberately no `loading.tsx` beside this file. A loading boundary puts
  // the page inside Suspense, so Next flushes a 200 shell before this
  // function runs — which turns `notFound()` into a soft 404 and demotes the
  // redirect below to a client-side hop. Correct status codes are worth more
  // than a skeleton on a response that takes a few hundred milliseconds.
  if (!isCanonicalTaxonSlug(raw)) permanentRedirect(genusHref(raw));

  const taxon = await fetchHigherTaxon("genus", raw);

  if (!taxon) notFound();

  // The literature search runs beside the family.
  const family = taxon.classification?.family;
  const crumbs = lineageCrumbs(taxon.classification, "genus", {
    label: taxon.name,
    italic: true,
  });

  return (
    <section className="m-2">
      <TaxonBreadcrumb items={crumbs} />
      <HigherTaxonHeader taxon={taxon} />

      <section className="mb-10" aria-labelledby="genus-images">
        <TaxonSpeciesList
          rank="genus"
          taxonKey={taxon.key}
          page={parseSpeciesPage(page)}
          href={genusHref(taxon.name)}
          title="Species in this genus"
          headingId="genus-images"
        />
      </section>

      <MorphospaceSection
        rank="genus"
        name={taxon.name}
        headingId="genus-morphospace"
      />

      <HigherTaxonTabs
        rank="genus"
        name={taxon.name}
        context={family}
        classificationCount={taxon.counts.speciesCount}
        memberLabel="species"
        imageCount={taxon.counts.imageCount}
        institutions={taxon.institutions}
        controls={
          <TaxonomyTreeControls treeId={TREE_ID} label="Filter species" />
        }
      >
        <TaxonomyTree
          id={TREE_ID}
          nodes={taxon.tree}
          bottomRank="species"
          highlightRank="genus"
          nodeCount={taxon.nodeCount}
        />
        <UnrecordedTaxaNote taxa="species" />
        <ColAttribution />
      </HigherTaxonTabs>
    </section>
  );
}
