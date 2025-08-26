import Link from "next/link";
import { SpeciesImages } from "./image_gallery";
import { SpeciesDescription } from "./description";
import { SpeciesClassification } from "./classification";
import { RedListStatus } from "./redlist_status";
import SpeciesDetailMapWrapper from "@/components/SpeciesDetailMapWrapper";
import { TaxonomyData } from "@/lib/speciesData";

// Define Occurrence type to match SpeciesMap component's expectation
import { Occurrence } from "@/lib/types";

interface SpeciesOverviewProps {
  speciesName: string;
  taxonomyData: TaxonomyData | null;
  gbifOccurrences: Occurrence[];
}

export function SpeciesOverview({
  speciesName,
  taxonomyData,
  gbifOccurrences,
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
        <div>
          <h2 className="text-2xl font-semibold mb-2">Distribution Map</h2>
          <p className="text-sm mb-2 text-gray-700 dark:text-gray-300">
            {gbifOccurrences.length > 0
              ? `Showing ${gbifOccurrences.length} occurrences. Use the zoom and pan controls to explore the map.`
              : "No occurrence data found."}
          </p>
          <SpeciesDetailMapWrapper occurrences={gbifOccurrences} />
        </div>
      </div>
    </div>
  );
}