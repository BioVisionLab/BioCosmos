import SpecimensTab from "../components/SpecimensTab";
import SpeciesHeader from "../components/SpeciesTitle";
import { getSpeciesData } from "@/lib/speciesData";

export default async function Page({ params }: { params: { speciesName: string } }) {
  const slug = params.speciesName ?? "";
  // getSpeciesData can parse the slug and fetch taxonomy for a prettier title
  const speciesData = await getSpeciesData(slug);
  const titleName = speciesData?.taxonomy?.species ?? slug;

  return (
    <main className="p-6 max-w-7xl mx-auto">
      <header className="mb-6 mt-4 text-center mx-auto">
        <SpeciesHeader taxonomy={speciesData?.taxonomy ?? null} name={titleName} />
      </header>
      <p className="text-sm text-gray-600 mb-6">Specimen images</p>
      {/* Show full gallery; hide the UMAP / similarity box */}
      {/* SpecimensTab is a client component and will handle fetching and pagination */}
      <SpecimensTab speciesName={slug} showAll={true} showUmap={false} />
    </main>
  );
}
