import type { Metadata } from "next";
import { notFound } from "next/navigation";

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
export default async function OrderPage() {
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
        <h2 id="order-images" className="text-2xl font-semibold mb-3">
          Species in this order
        </h2>
        <TaxonImageStrip
          images={pickRepresentatives(taxon.images, REPRESENTATIVE_IMAGE_LIMIT)}
        />
      </section>

      <section
        aria-labelledby="order-tree"
        className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg"
      >
        <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl flex flex-wrap items-center justify-between gap-3">
          <h2 id="order-tree" className="text-2xl font-semibold">
            Classification
          </h2>
          <TaxonomyTreeControls treeId={TREE_ID} label="Filter families" />
        </div>
        <div className="p-4">
          <TaxonomyTree
            id={TREE_ID}
            nodes={taxon.tree}
            bottomRank="family"
            highlightRank="order"
            nodeCount={taxon.nodeCount}
          />
          <p className="mt-3 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
            Families in grey are in the Catalogue of Life classification but
            have no images in the collection yet.
          </p>
          <ColAttribution />
        </div>
      </section>
    </section>
  );
}
