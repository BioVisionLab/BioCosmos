export enum GeneCategory {
  ProteinCoding,
  Rna,
  Pseudo,
  Other,
}

export interface GenomeAnnotation {
  name: string | null;
  provider: string | null;
  releaseDate: string | null;
  reportUrl: string | null;
  totalGenes: number | null;
  proteinCoding: number | null;
  nonCoding: number | null;
  pseudogenes: number | null;
  /** BUSCO: the share (0-1) of conserved single-copy genes found complete. */
  buscoComplete: number | null;
  buscoLineage: string | null;
}

/** A nuclear genome assembly, as NCBI Datasets reports it. */
export interface GenomeAssembly {
  accession: string;
  pairedAccession: string | null;
  assemblyName: string | null;
  /** A subspecies when the species itself has no assembly. */
  organismName: string | null;
  /** NCBI's designated reference, rather than the best of the rest. */
  isReference: boolean;
  assemblyLevel: string | null;
  releaseDate: string | null;
  submitter: string | null;
  sequencingTech: string | null;
  genomeSize: number | null;
  chromosomeCount: number | null;
  contigCount: number | null;
  contigN50: number | null;
  scaffoldCount: number | null;
  scaffoldN50: number | null;
  gcPercent: number | null;
  coverage: string | null;
  annotation: GenomeAnnotation | null;
}

export interface NuclearGenome {
  assembly: GenomeAssembly | null;
  /** Null when NCBI could not be asked; 0 when it has none. */
  assemblyCount: number | null;
}

/** The RefSeq mitochondrial genome NCBI holds for a species, if any. */
export interface MitogenomeReference {
  refseqAccession: string | null;
  genbankAccession: string | null;
  /** A subspecies when the species itself has no RefSeq mitogenome. */
  organismName: string | null;
  length: number | null;
  topology: string | null;
  geneCount: number | null;
  submissionDate: string | null;
}

export interface MarkerCount {
  marker: string;
  label: string;
  count: number;
  /** The Entrez query behind the count, for linking to the records. */
  query: string;
}

export interface MitochondrialSummary {
  reference: MitogenomeReference | null;
  /** Null when NCBI could not be asked; 0 when it has none. */
  sequenceCount: number | null;
  completeGenomeCount: number | null;
  markers: MarkerCount[];
  query: string;
}

export interface GeneticSummary {
  species: string;
  /** Annotated genes by NCBI gene type; null when they could not be fetched. */
  geneTypes: Record<string, number> | null;
  nuclear: NuclearGenome;
  mitochondrion: MitochondrialSummary;
  /** Some NCBI request failed or timed out, so something may be missing. */
  partial: boolean;
}

// Part of the request URL, so a browser or CDN holding a day-cached payload
// of an older shape misses it. Bump when the payload's fields change.
const GENETICS_PAYLOAD_VERSION = 2;

// A 503 means the backend is already waiting on NCBI for many species; it
// asks for a retry after this long.
const BUSY_RETRY_MS = 5000;

/**
 * What NCBI holds on a species' genes and mitochondrial DNA.
 *
 * Fetched through the backend, which identifies the site to NCBI, caches the
 * answer for a week and keeps inside NCBI's rate limits. Resolves null when
 * the name is not a species.
 */
async function fetchGeneticSummary(
  speciesName: string,
): Promise<GeneticSummary | null> {
  const url = `/api/genetics?species=${encodeURIComponent(speciesName)}&v=${GENETICS_PAYLOAD_VERSION}`;
  let response = await fetch(url, { headers: { Accept: "application/json" } });
  if (response.status === 503) {
    await new Promise((resolve) => setTimeout(resolve, BUSY_RETRY_MS));
    response = await fetch(url, { headers: { Accept: "application/json" } });
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(
      `Failed to fetch genetic data for ${speciesName}: ${response.status}`,
    );
  }
  return response.json();
}

/**
 * A sequence length in the unit a genomicist would use: `245.2 Mb` rather
 * than 245,173,502 bp. Split so the number and unit can be styled apart.
 */
function formatBases(length: number): { value: string; unit: string } {
  const scales: [number, string][] = [
    [1e9, "Gb"],
    [1e6, "Mb"],
    [1e3, "kb"],
  ];
  for (const [scale, unit] of scales) {
    if (length >= scale) {
      const scaled = length / scale;
      // Three significant figures: 2.30 Gb, 245 Mb, 17.2 Mb.
      const digits = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
      return { value: scaled.toFixed(digits), unit };
    }
  }
  return { value: String(length), unit: "bp" };
}

/** A genome assembly's page in NCBI Datasets. */
function genomeAssemblyUrl(accession: string): string {
  return `https://www.ncbi.nlm.nih.gov/datasets/genome/${encodeURIComponent(accession)}/`;
}

/** Every genome assembly NCBI holds for a taxon. */
function genomeAssembliesUrl(speciesName: string): string {
  return `https://www.ncbi.nlm.nih.gov/datasets/genome/?taxon=${encodeURIComponent(speciesName)}`;
}

/** An Entrez query as a link to its records in NCBI Nucleotide. */
function nucleotideSearchUrl(query: string): string {
  return `https://www.ncbi.nlm.nih.gov/nuccore/?term=${encodeURIComponent(query)}`;
}

function cleanGeneType(name: string): string {
  // If the name mix of lowercase and uppercase,
  // Usually indicates specific gene types like "tRNA" or "rRNA"
  if (/[a-z]/.test(name) && /[A-Z]/.test(name)) {
    return name;
  }
  // Otherwise, convert to Title Case for better readability
  return name
    .toLowerCase()
    .split(/[\s_-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function isProteinCoding(geneType: string): boolean {
  return geneType.toLowerCase().includes("protein");
}

function isRna(geneType: string): boolean {
  const lowerType = geneType.toLowerCase();
  return (
    lowerType.includes("rna") ||
    lowerType.includes("rrna") ||
    lowerType.includes("trna") ||
    lowerType.includes("snorna") ||
    lowerType.includes("snrna") ||
    lowerType.includes("mirna")
  );
}

function isPseudoGene(geneType: string): boolean {
  return geneType.toLowerCase().includes("pseudo");
}

function getGeneCategory(geneType: string): GeneCategory {
  if (isProteinCoding(geneType)) {
    return GeneCategory.ProteinCoding;
  } else if (isRna(geneType)) {
    return GeneCategory.Rna;
  } else if (isPseudoGene(geneType)) {
    return GeneCategory.Pseudo;
  } else {
    return GeneCategory.Other;
  }
}

// NCBI's gene types, spelled out. The abbreviation is kept beside the name
// because it is how a reader will meet the term in the literature.
const GENE_TYPE_NAMES: Record<string, string> = {
  protein_coding: "Protein-coding",
  pseudo: "Pseudogene",
  ncrna: "Non-coding RNA (ncRNA)",
  rrna: "Ribosomal RNA (rRNA)",
  trna: "Transfer RNA (tRNA)",
  snrna: "Small nuclear RNA (snRNA)",
  snorna: "Small nucleolar RNA (snoRNA)",
  scrna: "Small cytoplasmic RNA (scRNA)",
  mirna: "MicroRNA (miRNA)",
  lncrna: "Long non-coding RNA (lncRNA)",
  misc_rna: "Miscellaneous RNA",
  biological_region: "Biological region",
  other: "Other",
  unknown: "Unknown",
};

/** A reader-facing name for one of NCBI's gene types. */
function describeGeneType(geneType: string): string {
  return GENE_TYPE_NAMES[geneType.toLowerCase()] ?? cleanGeneType(geneType);
}

export {
  fetchGeneticSummary,
  formatBases,
  genomeAssembliesUrl,
  genomeAssemblyUrl,
  nucleotideSearchUrl,
  getGeneCategory,
  cleanGeneType,
  describeGeneType,
};
