import { getTaxonomyData } from "@/lib/speciesData"; // Import the function and the type
import Link from "next/link";
import TabsComponent from "./components/tabs";
import SpeciesHeader from "./components/title";

interface SpeciesPageProps {
  params: {
    speciesName: string; // This comes from the folder name [speciesName]
  };
}

// --- End GBIF API Fetching Function ---
export default async function SpeciesPage({ params }: SpeciesPageProps) {
  const resolvedParams = await params;
  const { speciesName: folderName } = resolvedParams;

  const taxonomyData = await getTaxonomyData(folderName);

  // Handle case where species data might not be found
  if (!taxonomyData) {
    return (
      <section className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold mb-6">Species Not Found</h1>
        <p>The requested species ({folderName}) could not be found.</p>
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
    <section>
      {" "}
      {/* Removed container from here, relies on Layout's container */}
      {/* Updated Breadcrumbs including Genus */}
      <nav className="text-sm mb-1 text-gray-600 dark:text-gray-400 flex items-center gap-2 border border-gray-300 dark:border-gray-600 bg-white/70 dark:bg-gray-800/70 backdrop-blur w-fit py-1 px-4 rounded-full shadow">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span>&gt;</span>
        {/* Link to Family (assuming Nymphalidae for now) */}
        <Link
          href={`/family/${taxonomyData.family}`}
          className="hover:underline"
        >
          {taxonomyData.family}
        </Link>
        <span>&gt;</span>
        {/* Link to the Genus page */}
        <Link
          href={`/genus/${taxonomyData.genus}`}
          className="hover:underline italic"
        >
          {taxonomyData.genus}
        </Link>
        <span>&gt;</span>
        <span className="italic text-gray-800 dark:text-gray-200">
          {taxonomyData.species}
        </span>
      </nav>
      {/* Optional: Add explicit "Back to Genus" link */}
      <div className="mb-4">
        <Link
          href={`/genus/${taxonomyData.genus}`}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          &larr; Back to <span className="italic">{taxonomyData.genus}</span>{" "}
          species
        </Link>
      </div>
      <SpeciesHeader taxonomy={taxonomyData} name={taxonomyData.species} />
      <div>
        <TabsComponent
          speciesName={taxonomyData.species}
          taxonomyData={taxonomyData}
        />
      </div>
    </section>
  );
}
