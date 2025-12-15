import Link from "next/link";
import dynamic from "next/dynamic";
import { SpeciesImageGallery } from "./ImageGallery";
import { SpeciesDescription } from "./TaxonSummary";
import { SpeciesClassification } from "./TaxonClassification";
import { RedListStatus } from "./IucnRedlist";
import { TaxonomyData } from "@/lib/speciesData";
import VisuallySimilarSpecies from "./SimilarSpecies";
import { LepTraits } from "@/lib/leptraits";
import { NoData } from "@/components/NoData";

const SpeciesDistribution = dynamic(
  () => import("@/app/species/[speciesName]/components/SpeciesMap"),
  {
    ssr: false,
    loading: () => (
      <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
        <NoData text="Loading map..." />
      </div>
    ),
  }
);

interface SpeciesOverviewProps {
  taxonomy: TaxonomyData | null;
  traits: LepTraits | null;
}

export function SpeciesOverview({ taxonomy, traits }: SpeciesOverviewProps) {
  if (!taxonomy) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species could not be found.</p>
        <Link
          href="/"
          className="text-blue-600 hover:underline mt-4 inline-block"
        >
          Return to homepage
        </Link>
      </section>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SpeciesImageGallery speciesName={taxonomy?.species ?? ""} />
          <SpeciesDescription
            traits={traits}
            species={taxonomy?.species ?? ""} // Use species from taxonomy or fallback to name
          />
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-1 space-y-6">
          <SpeciesClassification taxonomyData={taxonomy} />
          <RedListStatus statusCode={taxonomy?.redlistCategory ?? "Unknown"} />
          <SpeciesDistribution speciesName={taxonomy?.species ?? ""} />
        </div>
      </div>
      <div className="mt-6">
        <VisuallySimilarSpecies species={taxonomy?.species ?? ""} />
      </div>
    </div>
  );
}
