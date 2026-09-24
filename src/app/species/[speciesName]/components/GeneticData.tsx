import { NcbiGeneDataSourceInfo } from "@/components/Attribution";
import { IconContainer } from "@/components/IconContainer";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  DnaIcon,
  ProteinCodingIcon,
  PseudoGeneIcon,
  RnaIcon,
} from "@/components/ui/icons";
import {
  describeGeneType,
  fetchGenBankGeneCount,
  GeneCategory,
  getGeneCategory,
} from "@/lib/genetic";
import { formatNumberToLocaleString } from "@/lib/textUtils";
import { useEffect, useState } from "react";
import {
  commonIconClass,
  DataCard,
  DataSection,
  labelClass,
  rowClass,
  valueClass,
} from "./DataCards";

interface GeneticPageProps {
  speciesName: string;
}

interface GeneType {
  type: string;
  name: string;
  category: GeneCategory;
  count: number;
}

// Fixed order, so a category keeps its colour whichever of them a species
// has. The steps were chosen with the dataviz palette validator against the
// page surfaces: light and dark are separate steps, not one colour reused.
const CATEGORIES: {
  category: GeneCategory;
  label: string;
  swatch: string;
}[] = [
  {
    category: GeneCategory.ProteinCoding,
    label: "Protein-coding",
    swatch: "bg-[#009999] dark:bg-[#00a3a3]",
  },
  {
    category: GeneCategory.Rna,
    label: "Non-coding RNA",
    swatch: "bg-[#ad421f] dark:bg-[#bf4a22]",
  },
  {
    category: GeneCategory.Pseudo,
    label: "Pseudogene",
    swatch: "bg-[#7a5bc9] dark:bg-[#8f75da]",
  },
  {
    category: GeneCategory.Other,
    label: "Other",
    swatch: "bg-[#a8860a] dark:bg-[#aa8a0c]",
  },
];

const swatchFor = (category: GeneCategory) =>
  CATEGORIES.find((c) => c.category === category)?.swatch ?? "";

const formatShare = (count: number, total: number) => {
  const share = (count / total) * 100;
  // A handful of snoRNAs against thirteen thousand genes would round to 0%,
  // which reads as none.
  return share > 0 && share < 1 ? "<1%" : `${Math.round(share)}%`;
};

export function GeneticData({ speciesName }: GeneticPageProps) {
  // Keyed on the species the counts belong to, so switching species reads as
  // loading without an effect having to reset state first.
  const [result, setResult] = useState<{
    speciesName: string;
    counts: Record<string, number> | null;
  } | null>(null);
  const loading = result?.speciesName !== speciesName;
  const geneCounts = loading ? null : result.counts;

  useEffect(() => {
    let isMounted = true;
    fetchGenBankGeneCount(speciesName)
      .catch((error) => {
        console.error("Error fetching gene counts:", error);
        return null;
      })
      .then((counts) => {
        if (isMounted) {
          setResult({ speciesName, counts });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  if (loading) {
    return (
      <div className="mx-auto items-center">
        <TextLoading msg="Fetching genetic data..." />
      </div>
    );
  }

  const genes: GeneType[] = Object.entries(geneCounts ?? {})
    .filter(([, count]) => count > 0)
    .map(([type, count]) => ({
      type,
      name: describeGeneType(type),
      category: getGeneCategory(type),
      count,
    }))
    .sort((a, b) => b.count - a.count);
  const total = genes.reduce((sum, gene) => sum + gene.count, 0);

  if (total === 0) {
    return <NoData text="No genetic data available." />;
  }

  const inCategories = (...categories: GeneCategory[]) =>
    genes
      .filter((gene) => categories.includes(gene.category))
      .map((gene) => (
        <DataCard key={gene.type} title={gene.name}>
          <GeneCount gene={gene} total={total} />
        </DataCard>
      ));

  return (
    <div id="genetics-section">
      <DataSection title="Annotated Genes">
        <DataCard title="Gene Composition" wide>
          <GeneComposition genes={genes} total={total} />
        </DataCard>
      </DataSection>

      <DataSection title="Protein-coding and Pseudogenes">
        {inCategories(GeneCategory.ProteinCoding, GeneCategory.Pseudo)}
      </DataSection>

      <DataSection title="Non-coding RNA">
        {inCategories(GeneCategory.Rna)}
      </DataSection>

      <DataSection title="Other">{inCategories(GeneCategory.Other)}</DataSection>

      <div className="w-full flex justify-center items-center mt-12 mb-6">
        <NcbiGeneDataSourceInfo speciesName={speciesName} />
      </div>
    </div>
  );
}

/**
 * The total, then how it divides between the categories: one stacked bar,
 * labelled by a legend that carries each count, so no share is told by colour
 * alone. The cards below are the table view of the same numbers.
 */
function GeneComposition({
  genes,
  total,
}: {
  genes: GeneType[];
  total: number;
}) {
  const segments = CATEGORIES.map(({ category, label, swatch }) => ({
    category,
    label,
    swatch,
    count: genes
      .filter((gene) => gene.category === category)
      .reduce((sum, gene) => sum + gene.count, 0),
  })).filter((segment) => segment.count > 0);

  return (
    <div className={rowClass}>
      <div className="hidden sm:block">
        <IconContainer>
          <DnaIcon className={commonIconClass} />
        </IconContainer>
      </div>
      <div className="min-w-0 flex-1">
        <p className={valueClass}>
          {formatNumberToLocaleString(total)}{" "}
          <span className={labelClass}>gene{total === 1 ? "" : "s"}</span>
        </p>
        {/* 2px gaps between segments keep neighbours apart where colour
            alone would not. Hover shows a segment's count; the aria-label
            and the legend carry the same numbers for everyone else. */}
        <div
          className="mt-3 flex h-4 w-full gap-0.5 overflow-visible"
          role="img"
          aria-label={segments
            .map((s) => `${s.label}: ${formatNumberToLocaleString(s.count)}`)
            .join(", ")}
        >
          {segments.map((segment) => (
            <div
              key={segment.category}
              className="group relative h-full min-w-1 first:rounded-l last:rounded-r"
              style={{ flexGrow: segment.count, flexBasis: 0 }}
            >
              <div
                className={`h-full w-full rounded-[inherit] ${segment.swatch}`}
              />
              <div
                aria-hidden="true"
                className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-deep-mocha-200 bg-white px-2 py-1 text-xs text-deep-mocha-800 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 dark:border-deep-mocha-700 dark:bg-deep-mocha-900 dark:text-deep-mocha-100"
              >
                <span className="font-semibold">{segment.label}</span>{" "}
                {formatNumberToLocaleString(segment.count)} (
                {formatShare(segment.count, total)})
              </div>
            </div>
          ))}
        </div>
        <ul
          aria-hidden="true"
          className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-deep-mocha-600 dark:text-deep-mocha-300"
        >
          {segments.map((segment) => (
            <li
              key={segment.category}
              className="inline-flex items-center gap-1.5"
            >
              <span className={`size-3 rounded-sm ${segment.swatch}`} />
              {segment.label}
              <span className="text-deep-mocha-500 dark:text-deep-mocha-400">
                {formatNumberToLocaleString(segment.count)} ·{" "}
                {formatShare(segment.count, total)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function GeneCount({ gene, total }: { gene: GeneType; total: number }) {
  return (
    <div className={rowClass}>
      <IconContainer>
        <GeneIcon category={gene.category} />
      </IconContainer>
      <div>
        <p className={valueClass}>
          {formatNumberToLocaleString(gene.count)}{" "}
          <span className={labelClass}>
            gene{gene.count === 1 ? "" : "s"}
          </span>
        </p>
        <p className="inline-flex items-center gap-1.5 text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
          <span
            aria-hidden="true"
            className={`size-2.5 rounded-sm ${swatchFor(gene.category)}`}
          />
          {formatShare(gene.count, total)} of annotated genes
        </p>
      </div>
    </div>
  );
}

function GeneIcon({ category }: { category: GeneCategory }) {
  switch (category) {
    case GeneCategory.ProteinCoding:
      return <ProteinCodingIcon className={commonIconClass} />;
    case GeneCategory.Rna:
      return <RnaIcon className={commonIconClass} />;
    case GeneCategory.Pseudo:
      return <PseudoGeneIcon className={commonIconClass} />;
    default:
      return <DnaIcon className={commonIconClass} />;
  }
}
