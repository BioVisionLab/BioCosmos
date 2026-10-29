import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import { ColAttribution } from "@/components/Attribution";
import HigherTaxonHeader from "@/components/HigherTaxonHeader";
import HigherTaxonTabs from "@/components/HigherTaxonTabs";
import TaxonBreadcrumb, { lineageCrumbs } from "@/components/TaxonBreadcrumb";
import TaxonImageStrip from "@/components/TaxonImageStrip";
import TaxonomyTree, { UnrecordedTaxaNote } from "@/components/TaxonomyTree";
import TaxonomyTreeControls from "@/components/TaxonomyTreeControls";
import { ITALIC_COL_RANKS } from "@/lib/colTaxonomy";
import {
  type HigherRank,
  type HigherTaxon,
  REPRESENTATIVE_IMAGE_LIMIT,
  fetchHigherTaxon,
  pickRepresentatives,
} from "@/lib/higherTaxa";
import {
  type IntermediateRank,
  isCanonicalTaxonSlug,
  rankHref,
} from "@/lib/taxonSlug";

/** What a page lists, by the rank its tree stops at. */
const MEMBERS = {
  family: { plural: "families", count: "familyCount" },
  genus: { plural: "genera", count: "genusCount" },
  species: { plural: "species", count: "speciesCount" },
} as const;

type MemberRank = keyof typeof MEMBERS;

const MEMBER_RANK: Record<IntermediateRank | "subgenus", MemberRank> = {
  suborder: "family",
  superfamily: "family",
  subfamily: "genus",
  tribe: "genus",
  subtribe: "genus",
  subgenus: "species",
};

function memberCount(taxon: HigherTaxon, members: MemberRank): number | null {
  return taxon.counts[MEMBERS[members].count];
}

/**
 * A page for a rank between order and species that has no morphospace: a
 * suborder, superfamily, subfamily, tribe, subtribe or subgenus. The family
 * page's layout, with the lineage above it.
 */
export function HigherTaxonPage({
  taxon,
  rank,
  literatureName,
  literatureContext,
}: {
  taxon: HigherTaxon;
  rank: IntermediateRank | "subgenus";
  /** The name the literature search looks for, when not the page's name. */
  literatureName?: string;
  /** The taxon that search runs beside; see HigherTaxonTabs. */
  literatureContext?: string | null;
}) {
  const members = MEMBER_RANK[rank];
  const { plural } = MEMBERS[members];
  const treeId = `${rank}-classification-tree`;
  const imagesId = `${rank}-images`;

  return (
    <section className="m-2">
      <TaxonBreadcrumb
        items={lineageCrumbs(taxon.classification, rank, {
          label: taxon.name,
          italic: ITALIC_COL_RANKS.has(rank),
        })}
      />
      <HigherTaxonHeader taxon={taxon} />

      <section className="mb-10" aria-labelledby={imagesId}>
        <h2 id={imagesId} className="text-2xl font-semibold mb-3">
          Species in this {rank}
        </h2>
        <TaxonImageStrip
          images={pickRepresentatives(taxon.images, REPRESENTATIVE_IMAGE_LIMIT)}
        />
      </section>

      <HigherTaxonTabs
        rank={rank}
        name={literatureName ?? taxon.name}
        context={literatureContext}
        classificationCount={memberCount(taxon, members)}
        memberLabel={plural}
        imageCount={taxon.counts.imageCount}
        institutions={taxon.institutions}
        controls={
          <TaxonomyTreeControls treeId={treeId} label={`Filter ${plural}`} />
        }
      >
        <TaxonomyTree
          id={treeId}
          nodes={taxon.tree}
          bottomRank={members}
          highlightRank={rank}
          nodeCount={taxon.nodeCount}
        />
        <UnrecordedTaxaNote taxa={plural} />
        <ColAttribution />
      </HigherTaxonTabs>
    </section>
  );
}

export function higherTaxonMetadata(
  taxon: HigherTaxon | null,
  rank: HigherRank,
  canonical: string | null,
): Metadata {
  if (!taxon)
    return { title: `${rank[0].toUpperCase()}${rank.slice(1)} not found` };

  const { counts } = taxon;
  const parts = [
    counts.familyCount !== null
      ? `${counts.familyCount.toLocaleString()} families`
      : null,
    counts.genusCount !== null
      ? `${counts.genusCount.toLocaleString()} genera`
      : null,
    `${counts.speciesCount.toLocaleString()} species`,
  ].filter((part): part is string => part !== null);

  return {
    title: `${taxon.name} — ${rank}`,
    description:
      `${parts.join(", ")} and ${counts.imageCount.toLocaleString()} ` +
      `specimen images in the butterfly ${rank} ${taxon.name}.`,
    alternates: canonical ? { canonical } : undefined,
  };
}

interface NameParams {
  params: Promise<{ name: string }>;
}

/**
 * `generateMetadata` and the page for `/{rank}/[name]`, the route shape the
 * family-group ranks share. Each route file only names its rank.
 */
export function intermediateRankRoute(rank: IntermediateRank) {
  async function generateMetadata({ params }: NameParams): Promise<Metadata> {
    const { name } = await params;
    const taxon = await fetchHigherTaxon(rank, decodeURIComponent(name));

    return higherTaxonMetadata(
      taxon,
      rank,
      taxon ? rankHref(rank, taxon.name) : null,
    );
  }

  async function Page({ params }: NameParams) {
    const { name } = await params;
    const raw = decodeURIComponent(name);

    // One taxon, one URL; see the family page. No loading.tsx beside these
    // routes either, for the reason given there.
    if (!isCanonicalTaxonSlug(raw)) {
      const canonical = rankHref(rank, raw);

      if (canonical) permanentRedirect(canonical);
    }

    const taxon = await fetchHigherTaxon(rank, raw);

    if (!taxon) notFound();

    return <HigherTaxonPage taxon={taxon} rank={rank} />;
  }

  return { generateMetadata, Page };
}
