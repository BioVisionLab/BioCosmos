import { fetchSpeciesData } from "@/lib/speciesPage";

import SpecimenGallery from "../components/SpecimenGallery";

// API_HOST is unavailable during the Docker build; see the species page.
export const dynamic = "force-dynamic";

export default async function SpeciesImageGalleryPage({
  params,
}: {
  params: Promise<{ speciesName: string }>;
}) {
  const { speciesName } = await params;
  // Only the header comes from this; the gallery below loads on its own, so
  // an outage drops the header rather than the page.
  const speciesData = await fetchSpeciesData(speciesName).catch(() => null);

  return (
    <SpecimenGallery
      speciesName={speciesName}
      taxonomy={speciesData?.taxonomy ?? null}
    />
  );
}
