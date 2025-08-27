import Link from "next/link";
import dynamic from "next/dynamic";
import { SpeciesImages } from "./image_gallery";
import { SpeciesDescription } from "./description";
import { SpeciesClassification } from "./classification";
import { RedListStatus } from "./redlist_status";
import { TaxonomyData } from "@/lib/speciesData";

const SpeciesDistribution = dynamic(
  () => import("@/app/species/[speciesName]/components/SpeciesMap"),
  {
    ssr: false,
    loading: () => (
      <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
        <span className="text-gray-500">Loading map...</span>
      </div>
    ),
  }
);

interface SpeciesOverviewProps {
  speciesName: string;
  taxonomyData: TaxonomyData | null;
}

export function SpeciesOverview({
  speciesName,
  taxonomyData,
}: SpeciesOverviewProps) {
  if (!taxonomyData) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species ({speciesName}) could not be found.</p>
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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2">
        <SpeciesImages speciesName={speciesName} />
        <SpeciesDescription
          description={taxonomyData?.description ?? "No description available."}
          species={taxonomyData?.species ?? ""} // Use species from taxonomy or fallback to name
        />
      </div>

      {/* Right Column: Details */}
      <div className="lg:col-span-1 space-y-6">
        <SpeciesClassification taxonomyData={taxonomyData} />
        <RedListStatus
          statusCode={taxonomyData?.redlistCategory ?? "Unknown"}
        />
        <SpeciesDistribution speciesName={speciesName} />
      </div>
    </div>
  );
}
