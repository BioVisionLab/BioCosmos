import SpecimenGallery from "../components/SpecimenGallery";

export default function SpeciesImageGalleryPage({ params }: { params: { speciesName: string } }) {
  const speciesName = params?.speciesName ?? "";
  return <SpecimenGallery speciesName={speciesName} />;
}
