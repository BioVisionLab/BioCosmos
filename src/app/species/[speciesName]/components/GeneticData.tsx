import { NcbiAttribution } from "@/components/Attribution";
import { TextLoading } from "@/components/Loadings";
import { NoData } from "@/components/NoData";
import {
  DnaIcon,
  ProteinCodingIcon,
  PseudoGeneIcon,
  RnaIcon,
} from "@/components/ui/Genetics";
import {
  cleanGeneType,
  fetchGenBankGeneCount,
  GeneCategory,
  getGeneCategory,
} from "@/lib/genetic";
import { useEffect, useState } from "react";

interface GeneticPageProps {
  speciesName: string;
}

export function GeneticData({ speciesName }: GeneticPageProps) {
  const [geneCounts, setGeneCounts] = useState<Record<string, number> | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    const fetchData = async () => {
      try {
        const counts = await fetchGenBankGeneCount(speciesName);
        if (isMounted) {
          setGeneCounts(counts);
        }
      } catch (error) {
        console.error("Error fetching gene counts:", error);
        if (isMounted) {
          setGeneCounts(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  if (loading) {
    return (
      <div className="mx-auto items-center">
        <TextLoading text="Loading genetic data..." />
      </div>
    );
  }

  if (!geneCounts) {
    return (
      <div className="mx-auto items-center">
        <NoData text="No genetic data available." />
      </div>
    );
  }

  return (
    <div className="mx-auto items-center">
      <div>
        <h3 className="text-lg">Sequenced genes</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(geneCounts).map(([type, count]) => (
            <GeneCounts key={type} geneType={type} count={count} />
          ))}
        </div>
      </div>
      <NcbiAttribution isLarge={true} />
    </div>
  );
}

function GeneCounts({ geneType, count }: { geneType: string; count: number }) {
  const geneCategory = getGeneCategory(geneType);
  const cleanedName = cleanGeneType(geneType);
  const containerClass =
    "rounded-xl bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center p-2 mr-2";
  return (
    <div className="flex flex-col-2 items-center">
      <div className={containerClass}>
        <GeneIcon category={geneCategory} />
      </div>
      <div className="my-2 py-2">
        <p className="text-lg font-semibold">{cleanedName}</p>
        <p className="text-2xl font-bold">{count}</p>
      </div>
    </div>
  );
}

function GeneIcon({ category }: { category: GeneCategory }) {
  const className = "w-12 h-12 fill-teal-500 mb-2";
  switch (category) {
    case GeneCategory.ProteinCoding:
      return <ProteinCodingIcon key="protein-coding" className={className} />;
    case GeneCategory.Rna:
      return <RnaIcon key="rna" className={className} />;
    case GeneCategory.Pseudo:
      return <PseudoGeneIcon key="pseudo" className={className} />;
    default:
      return <DnaIcon key="dna" className={className} />;
  }
}
