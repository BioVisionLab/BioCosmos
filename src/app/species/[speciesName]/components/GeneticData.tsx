import {
  NcbiGeneDataNote,
  NcbiGeneDataSourceInfo,
} from "@/components/Attribution";
import Note from "@/components/Note";
import { IconContainer } from "@/components/IconContainer";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  AnnotationIcon,
  AssemblyIcon,
  ChromosomeIcon,
  DnaIcon,
  MarkerIcon,
  MitogenomeIcon,
  ProteinCodingIcon,
  PseudoGeneIcon,
  RnaIcon,
} from "@/components/ui/icons";
import {
  describeGeneType,
  fetchGeneticSummary,
  formatBases,
  GeneCategory,
  type GeneticSummary,
  type GenomeAnnotation,
  type GenomeAssembly,
  genomeAssembliesUrl,
  genomeAssemblyUrl,
  getGeneCategory,
  type MarkerCount,
  type MitochondrialSummary,
  type MitogenomeReference,
  type NuclearGenome,
  nucleotideSearchUrl,
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

const linkClass =
  "underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300";
const noteClass = "text-sm text-deep-mocha-500 dark:text-deep-mocha-400";

export function GeneticData({ speciesName }: GeneticPageProps) {
  // Keyed on the species the summary belongs to, so switching species reads
  // as loading without an effect having to reset state first.
  const [result, setResult] = useState<{
    speciesName: string;
    summary: GeneticSummary | null;
  } | null>(null);
  const loading = result?.speciesName !== speciesName;
  const summary = loading ? null : result.summary;

  useEffect(() => {
    let isMounted = true;
    fetchGeneticSummary(speciesName)
      .catch((error) => {
        console.error("Error fetching genetic data:", error);
        return null;
      })
      .then((summary) => {
        if (isMounted) {
          setResult({ speciesName, summary });
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

  const genes: GeneType[] = Object.entries(summary?.geneTypes ?? {})
    .filter(([, count]) => count > 0)
    .map(([type, count]) => ({
      type,
      name: describeGeneType(type),
      category: getGeneCategory(type),
      count,
    }))
    .sort((a, b) => b.count - a.count);
  const total = genes.reduce((sum, gene) => sum + gene.count, 0);
  const mito = summary?.mitochondrion;
  const hasMito = !!mito && (!!mito.reference || (mito.sequenceCount ?? 0) > 0);
  const nuclear = summary?.nuclear;
  const hasNuclear =
    !!nuclear && (!!nuclear.assembly || (nuclear.assemblyCount ?? 0) > 0);

  if (!summary || (total === 0 && !hasMito && !hasNuclear)) {
    return (
      <div id="genetics-section">
        <NoData
          text={
            summary?.partial
              ? "Genetic data could not be loaded from NCBI. Please try again later."
              : "No genetic data available."
          }
        />
      </div>
    );
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
      {summary.partial && (
        <div className="mb-4" role="status">
          <Note label="Incomplete results">
            <p>
              Some data could not be loaded from NCBI, so this summary may be
              incomplete. Please try again later.
            </p>
          </Note>
        </div>
      )}

      {hasNuclear && nuclear && (
        <NuclearGenomeSection nuclear={nuclear} speciesName={speciesName} />
      )}

      {total > 0 && (
        <>
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

          <DataSection title="Other">
            {inCategories(GeneCategory.Other)}
          </DataSection>
        </>
      )}

      {hasMito && mito && (
        <MitochondrialDna mito={mito} speciesName={speciesName} />
      )}

      <div className="w-full mt-12 mb-6">
        <NcbiGeneDataNote />
        <NcbiGeneDataSourceInfo speciesName={speciesName} />
      </div>
    </div>
  );
}

/** The year of an ISO date, for "submitter, year" lines. */
const yearOf = (date: string | null) => date?.slice(0, 4) ?? null;

function BasesValue({ length, suffix }: { length: number; suffix?: string }) {
  const { value, unit } = formatBases(length);
  return (
    <p className={valueClass}>
      {value}{" "}
      <span className={labelClass}>
        {unit}
        {suffix ? ` ${suffix}` : ""}
      </span>
    </p>
  );
}

/**
 * The nuclear genome: the assembly NCBI designates as the species' reference
 * or, without one, the most complete of its assemblies; how contiguous that
 * assembly is; its annotation; and how many assemblies there are in all.
 */
function NuclearGenomeSection({
  nuclear,
  speciesName,
}: {
  nuclear: NuclearGenome;
  speciesName: string;
}) {
  const assembly = nuclear.assembly;
  const count = nuclear.assemblyCount ?? 0;
  return (
    <DataSection title="Nuclear Genome">
      {assembly && (
        <DataCard
          title={
            assembly.isReference
              ? "Reference Genome"
              : "Best Available Assembly"
          }
        >
          <GenomeAssemblySummary
            assembly={assembly}
            speciesName={speciesName}
          />
        </DataCard>
      )}
      {assembly &&
        (assembly.contigN50 != null || assembly.scaffoldN50 != null) && (
          <DataCard title="Assembly Contiguity">
            <AssemblyContiguity assembly={assembly} />
          </DataCard>
        )}
      {assembly?.annotation && (
        <DataCard title="Genome Annotation">
          <AnnotationSummary annotation={assembly.annotation} />
        </DataCard>
      )}
      {count > 0 && (
        <DataCard title="Genome Assemblies in NCBI">
          <div className={rowClass}>
            <IconContainer>
              <DnaIcon className={commonIconClass} />
            </IconContainer>
            <div className="min-w-0">
              <p className={valueClass}>
                {formatNumberToLocaleString(count)}{" "}
                <span className={labelClass}>
                  assembl{count === 1 ? "y" : "ies"}
                </span>
              </p>
              <p className={noteClass}>
                <a
                  href={genomeAssembliesUrl(speciesName.replace(/_/g, " "))}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={linkClass}
                >
                  View in NCBI Datasets
                </a>
              </p>
            </div>
          </div>
        </DataCard>
      )}
    </DataSection>
  );
}

function GenomeAssemblySummary({
  assembly,
  speciesName,
}: {
  assembly: GenomeAssembly;
  speciesName: string;
}) {
  const level = assembly.assemblyLevel?.toLowerCase();
  const structure = [
    level && `${level}-level`,
    assembly.chromosomeCount != null &&
      assembly.chromosomeCount > 0 &&
      `${formatNumberToLocaleString(assembly.chromosomeCount)} chromosome${
        assembly.chromosomeCount === 1 ? "" : "s"
      }`,
  ].filter(Boolean);
  const provenance = [assembly.submitter, yearOf(assembly.releaseDate)]
    .filter(Boolean)
    .join(", ");
  const fromOther =
    assembly.organismName &&
    assembly.organismName.toLowerCase() !==
      speciesName.replace(/_/g, " ").toLowerCase();
  return (
    <div className={rowClass}>
      <IconContainer>
        <ChromosomeIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        {assembly.genomeSize != null && (
          <BasesValue length={assembly.genomeSize} />
        )}
        {structure.length > 0 && (
          <p className={noteClass}>{structure.join(" · ")}</p>
        )}
        {provenance && <p className={noteClass}>{provenance}</p>}
        <p className={noteClass}>
          <a
            href={genomeAssemblyUrl(assembly.accession)}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClass}
          >
            {assembly.accession}
          </a>
          {assembly.assemblyName && <> ({assembly.assemblyName})</>}
          {fromOther && (
            <>
              {" "}
              from <i>{assembly.organismName}</i>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

function AssemblyContiguity({ assembly }: { assembly: GenomeAssembly }) {
  const pieces = (count: number | null, noun: string) =>
    count != null &&
    `${formatNumberToLocaleString(count)} ${noun}${count === 1 ? "" : "s"}`;
  const scaffolds = [
    assembly.scaffoldN50 != null &&
      `Scaffold N50 ${Object.values(formatBases(assembly.scaffoldN50)).join(" ")}`,
    pieces(assembly.scaffoldCount, "scaffold"),
    pieces(assembly.contigCount, "contig"),
  ].filter(Boolean);
  const composition = [
    assembly.gcPercent != null && `GC ${assembly.gcPercent}%`,
    assembly.coverage && `${assembly.coverage}× coverage`,
  ].filter(Boolean);
  return (
    <div className={rowClass}>
      <IconContainer>
        <AssemblyIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        {assembly.contigN50 != null && (
          <BasesValue length={assembly.contigN50} suffix="contig N50" />
        )}
        {scaffolds.length > 0 && (
          <p className={noteClass}>{scaffolds.join(" · ")}</p>
        )}
        {composition.length > 0 && (
          <p className={noteClass}>{composition.join(" · ")}</p>
        )}
        {assembly.sequencingTech && (
          <p className={noteClass}>{assembly.sequencingTech}</p>
        )}
      </div>
    </div>
  );
}

function AnnotationSummary({ annotation }: { annotation: GenomeAnnotation }) {
  const genes = [
    annotation.proteinCoding != null &&
      `${formatNumberToLocaleString(annotation.proteinCoding)} protein-coding`,
    annotation.nonCoding != null &&
      `${formatNumberToLocaleString(annotation.nonCoding)} non-coding`,
    annotation.pseudogenes != null &&
      `${formatNumberToLocaleString(annotation.pseudogenes)} pseudogenes`,
  ].filter(Boolean);
  const release = [annotation.provider, annotation.releaseDate]
    .filter(Boolean)
    .join(", ");
  return (
    <div className={rowClass}>
      <IconContainer>
        <AnnotationIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        {annotation.totalGenes != null && (
          <p className={valueClass}>
            {formatNumberToLocaleString(annotation.totalGenes)}{" "}
            <span className={labelClass}>
              gene{annotation.totalGenes === 1 ? "" : "s"}
            </span>
          </p>
        )}
        {genes.length > 0 && <p className={noteClass}>{genes.join(" · ")}</p>}
        {annotation.buscoComplete != null && (
          // BUSCO: how many genes expected in every member of the lineage
          // were found complete — the usual yardstick of completeness.
          <p className={noteClass}>
            BUSCO {(annotation.buscoComplete * 100).toFixed(1)}% complete
            {annotation.buscoLineage && <> ({annotation.buscoLineage})</>}
          </p>
        )}
        {release && (
          <p className={noteClass}>
            {annotation.reportUrl ? (
              <a
                href={annotation.reportUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={linkClass}
              >
                {release}
              </a>
            ) : (
              release
            )}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * The reference mitogenome, how many mitochondrial records GenBank holds,
 * and how they spread over the markers systematists sequence. For most
 * species without a sequenced genome this is all the genetic data there is.
 */
function MitochondrialDna({
  mito,
  speciesName,
}: {
  mito: MitochondrialSummary;
  speciesName: string;
}) {
  const markers = mito.markers.filter((marker) => marker.count > 0);
  return (
    <>
      <DataSection title="Mitochondrial DNA">
        {mito.reference && (
          <DataCard title="Reference Mitogenome">
            <ReferenceMitogenome
              reference={mito.reference}
              speciesName={speciesName}
            />
          </DataCard>
        )}
        {(mito.sequenceCount ?? 0) > 0 && (
          <DataCard title="Sequences in GenBank">
            <SequenceCount mito={mito} />
          </DataCard>
        )}
      </DataSection>

      <DataSection title="Mitochondrial Markers">
        {markers.map((marker) => (
          <DataCard key={marker.marker} title={marker.label}>
            <MarkerRecords marker={marker} />
          </DataCard>
        ))}
      </DataSection>
    </>
  );
}

function ReferenceMitogenome({
  reference,
  speciesName,
}: {
  reference: MitogenomeReference;
  speciesName: string;
}) {
  const accession = reference.refseqAccession ?? reference.genbankAccession;
  const details = [
    reference.geneCount != null &&
      `${formatNumberToLocaleString(reference.geneCount)} genes`,
    reference.topology?.toLowerCase(),
  ].filter(Boolean);
  const fromOther =
    reference.organismName &&
    reference.organismName.toLowerCase() !==
      speciesName.replace(/_/g, " ").toLowerCase();
  return (
    <div className={rowClass}>
      <IconContainer>
        <MitogenomeIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        {reference.length != null && (
          <p className={valueClass}>
            {formatNumberToLocaleString(reference.length)}{" "}
            <span className={labelClass}>bp</span>
          </p>
        )}
        {details.length > 0 && (
          <p className={noteClass}>{details.join(" · ")}</p>
        )}
        {accession && (
          <p className={noteClass}>
            <a
              href={`https://www.ncbi.nlm.nih.gov/nuccore/${encodeURIComponent(accession)}`}
              target="_blank"
              rel="noopener noreferrer"
              className={linkClass}
            >
              {accession}
            </a>
            {fromOther && (
              <>
                {" "}
                from <i>{reference.organismName}</i>
              </>
            )}
          </p>
        )}
      </div>
    </div>
  );
}

function SequenceCount({ mito }: { mito: MitochondrialSummary }) {
  const count = mito.sequenceCount ?? 0;
  const complete = mito.completeGenomeCount;
  return (
    <div className={rowClass}>
      <IconContainer>
        <DnaIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        <p className={valueClass}>
          {formatNumberToLocaleString(count)}{" "}
          <span className={labelClass}>record{count === 1 ? "" : "s"}</span>
        </p>
        {complete != null && (
          <p className={noteClass}>
            {complete > 0 ? formatNumberToLocaleString(complete) : "No"}{" "}
            complete mitogenome{complete === 1 ? "" : "s"}
          </p>
        )}
        <p className={noteClass}>
          <a
            href={nucleotideSearchUrl(mito.query)}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClass}
          >
            View in NCBI Nucleotide
          </a>
        </p>
      </div>
    </div>
  );
}

function MarkerRecords({ marker }: { marker: MarkerCount }) {
  return (
    <div className={rowClass}>
      <IconContainer>
        <MarkerIcon className={commonIconClass} />
      </IconContainer>
      <div className="min-w-0">
        <p className={valueClass}>
          {formatNumberToLocaleString(marker.count)}{" "}
          <span className={labelClass}>
            record{marker.count === 1 ? "" : "s"}
          </span>
        </p>
        <p className={noteClass}>
          <a
            href={nucleotideSearchUrl(marker.query)}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClass}
          >
            View in NCBI Nucleotide
          </a>
        </p>
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
          <span className={labelClass}>gene{gene.count === 1 ? "" : "s"}</span>
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
