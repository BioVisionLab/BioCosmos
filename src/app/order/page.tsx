import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ColAttribution } from "@/components/Attribution";
import HigherTaxonHeader from "@/components/HigherTaxonHeader";
import HigherTaxonTabs from "@/components/HigherTaxonTabs";
import TaxonBreadcrumb from "@/components/TaxonBreadcrumb";
import TaxonSpeciesList, {
  parseSpeciesPage,
} from "@/components/TaxonSpeciesList";
import TaxonomyTree, { UnrecordedTaxaNote } from "@/components/TaxonomyTree";
import TaxonomyTreeControls from "@/components/TaxonomyTreeControls";
import { fetchHigherTaxon } from "@/lib/higherTaxa";
import { ORDER_NAME, ORDER_PATH } from "@/lib/taxonSlug";

// Never pre-rendered at build time: API_HOST is unavailable during the Docker
// build. The thirty-day cache lives on the fetch in @/lib/higherTaxa and
// survives this flag; see the note there before adding `fetchCache` here.
export const dynamic = "force-dynamic";

const TREE_ID = "order-classification-tree";

export async function generateMetadata(): Promise<Metadata> {
  const taxon = await fetchHigherTaxon("order", ORDER_NAME);

  if (!taxon) return { title: "Order not found" };

  return {
    title: `${taxon.name} — order`,
    description:
      `${taxon.counts.familyCount?.toLocaleString() ?? "—"} families, ` +
      `${taxon.counts.speciesCount.toLocaleString()} species and ` +
      `${taxon.counts.imageCount.toLocaleString()} specimen images in the ` +
      `order ${taxon.name}, classified by Catalogue of Life.`,
    alternates: { canonical: ORDER_PATH },
  };
}

/**
 * The one order the collection covers, as Catalogue of Life classifies it.
 *
 * Unlike the family and genus pages, the tree is the backbone's rather than
 * the collection's: every family CoL places in the order is listed, and those
 * with nothing photographed here are shown without a link.
 */
export default async function OrderPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string | string[] }>;
}) {
  const { page } = await searchParams;
  // No loading.tsx beside this file, for the reason given on the family page:
  // it would turn notFound() into a soft 404.
  const taxon = await fetchHigherTaxon("order", ORDER_NAME);

  if (!taxon) notFound();

  return (
    <section className="m-2">
      <TaxonBreadcrumb
        items={[{ label: "Home", href: "/" }, { label: taxon.name }]}
      />
      <HigherTaxonHeader taxon={taxon} />

      <section className="mb-10" aria-labelledby="order-images">
        <TaxonSpeciesList
          rank="order"
          taxonKey={taxon.key}
          page={parseSpeciesPage(page)}
          href={ORDER_PATH}
          title="Species in this order"
          headingId="order-images"
        />
      </section>

      <HigherTaxonTabs
        rank="order"
        name={taxon.name}
        classificationCount={taxon.counts.familyCount}
        memberLabel="families"
        imageCount={taxon.counts.imageCount}
        institutions={taxon.institutions}
        controls={
          <TaxonomyTreeControls treeId={TREE_ID} label="Filter families" />
        }
      >
        <TaxonomyTree
          id={TREE_ID}
          nodes={taxon.tree}
          bottomRank="family"
          highlightRank="order"
          nodeCount={taxon.nodeCount}
        />
        <UnrecordedTaxaNote taxa="families" />
        <ColAttribution />
      </HigherTaxonTabs>
    </section>
  );
}
