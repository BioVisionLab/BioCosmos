import { NcbiAttribution, NcbiLink } from "@/components/Attribution";
import { IconContainer } from "@/components/IconContainer";
import Info from "@/components/Info";
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
import { formatNumberToLocaleString } from "@/lib/textUtils";
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
        <TextLoading msg="Fetching genetic data..." />
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
    <div id="genetics-section">
      <div className="mb-4">
        <Info>
          <p>
            Genetic information is fetched automatically from <NcbiLink />. It
            includes only sequenced genes currently available for this species.
          </p>
        </Info>
      </div>
      <div className="mx-auto items-center">
        <div>
          <h3 className="text-lg">Sequenced genes</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(geneCounts).map(([geneType, count]) => (
              <GeneCounts key={geneType} geneType={geneType} count={count} />
            ))}
          </div>
        </div>
        <NcbiAttribution isLarge={true} />
      </div>
    </div>
  );
}

function GeneCounts({ geneType, count }: { geneType: string; count: number }) {
  const geneCategory = getGeneCategory(geneType);
  const cleanedName = cleanGeneType(geneType);
  const geneCount = formatNumberToLocaleString(count);

  return (
    <div className="flex flex-col-2 items-center">
      <IconContainer>
        <GeneIcon category={geneCategory} />
      </IconContainer>
      <div className="my-2 py-2">
        <p className="text-lg font-semibold">{cleanedName}</p>
        <p className="text-2xl font-bold">{geneCount}</p>
      </div>
    </div>
  );
}

function GeneIcon({ category }: { category: GeneCategory }) {
  const className = "w-12 h-12 fill-pacific-blue-500 mb-2";
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
