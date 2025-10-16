const GENBANK_API_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2";

export enum GeneCategory {
  ProteinCoding,
  Rna,
  Pseudo,
  Other,
}

async function queryGenBankData(speciesName: string): Promise<any> {
  try {
    const response = await fetch(
      `${GENBANK_API_URL}/gene/taxon/${encodeURIComponent(speciesName)}/counts`
    );
    if (!response.ok) {
      throw new Error(
        `Failed to fetch GenBank data for ${speciesName}: ${response.statusText}`
      );
    }
    return response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}

async function fetchGenBankGeneCount(
  speciesName: string
): Promise<Record<string, number> | null> {
  const data = await queryGenBankData(speciesName);
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    console.log("Invalid response format.");
    return null;
  }

  const report = (data as any).report ?? (data as any).gene_counts;

  if (!report || !Array.isArray(report)) {
    console.log("No gene counts found.");
    return null;
  }

  const counts: Record<string, number> = {};
  for (const item of report as Array<any>) {
    const geneType =
      typeof item["gene_type"] === "string" ? item["gene_type"] : "unknown";
    const count = typeof item["count"] === "number" ? item["count"] : 0;
    counts[geneType] = count;
  }

  return counts;
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

export { fetchGenBankGeneCount, getGeneCategory, cleanGeneType };
