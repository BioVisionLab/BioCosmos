import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import {
  HigherTaxonPage,
  higherTaxonMetadata,
} from "@/components/HigherTaxonPage";
import { fetchHigherTaxon } from "@/lib/higherTaxa";
import { isCanonicalTaxonSlug, subgenusHref } from "@/lib/taxonSlug";

// See the note on the family page: the thirty-day cache is on the fetch, not
// on this segment, and this flag does not defeat it.
export const dynamic = "force-dynamic";

interface SubgenusPageProps {
  params: Promise<{ genusName: string; subgenusName: string }>;
}

async function resolve(params: SubgenusPageProps["params"]) {
  const { genusName, subgenusName } = await params;

  return {
    genus: decodeURIComponent(genusName),
    subgenus: decodeURIComponent(subgenusName),
  };
}

export async function generateMetadata({
  params,
}: SubgenusPageProps): Promise<Metadata> {
  const { genus, subgenus } = await resolve(params);
  const taxon = await fetchHigherTaxon("subgenus", `${genus}/${subgenus}`);

  return higherTaxonMetadata(
    taxon,
    "subgenus",
    taxon ? subgenusHref(genus, subgenus) : null,
  );
}

/**
 * A subgenus, under its genus: a subgenus name is unique only within one.
 */
export default async function SubgenusPage({ params }: SubgenusPageProps) {
  const { genus, subgenus } = await resolve(params);

  // One taxon, one URL; see the family page. No loading.tsx beside this file
  // either, for the reason given there.
  if (!isCanonicalTaxonSlug(genus) || !isCanonicalTaxonSlug(subgenus)) {
    permanentRedirect(subgenusHref(genus, subgenus));
  }

  const taxon = await fetchHigherTaxon("subgenus", `${genus}/${subgenus}`);

  if (!taxon) notFound();

  // The bare subgenus is what a title names, searched beside its genus.
  const name = taxon.classification?.subgenus ?? subgenus;
  const genusName = taxon.classification?.genus || genus;

  return (
    <HigherTaxonPage
      taxon={taxon}
      rank="subgenus"
      literatureName={name}
      literatureContext={genusName}
    />
  );
}
