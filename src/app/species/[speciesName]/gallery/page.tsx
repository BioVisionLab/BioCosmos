import SpecimenGallery from "../components/SpecimenGallery";

export default async function SpeciesImageGalleryPage({ params }: { params: Promise<{ speciesName: string }> }) {
  const { speciesName } = await params;
  return <SpecimenGallery speciesName={speciesName} />;
}
