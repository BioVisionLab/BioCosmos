import { fetchSimilarImg } from "@/lib/speciesList";
import Image from "next/image";
import { useEffect, useState } from "react";

function SimilarSpecies({
  species,
  imgIds,
}: {
  species: string;
  imgIds: string[];
}) {
  if (imgIds.length === 0) {
    return null; // Don't render anything if there are no similar species
  }
  return (
    <div className="mt-4">
      <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
      <p className="text-gray-500 dark:text-gray-400">
        Similar species to <span className="italic">{species}</span> based on
        image analysis.
      </p>
      <SimilarSpeciesImageGallery imgIds={imgIds} />
    </div>
  );
}

function SimilarSpeciesImageGallery({ imgIds }: { imgIds: string[] }) {
  return (
    <div className="mt-2 p-2 border border-gray-300 dark:border-gray-600 overflow-x-auto rounded-xl">
      {imgIds.map((imgId) => (
        <SimilarSpeciesImage key={imgId} imgId={imgId} />
      ))}
    </div>
  );
}

function SimilarSpeciesImage({ imgId }: { imgId: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchImage = async () => {
      try {
        const response = await fetchSimilarImg(imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      }
    };
    fetchImage();
  }, [imgId]);

  return (
    imageUrl && (
      <div className="relative w-32 h-32 inline-block m-2 overflow-hidden p-2">
        <Image
          src={imageUrl}
          alt={`Similar species image ${imgId}`}
          fill
          className="object-fill"
        />
      </div>
    )
  );
}

export default SimilarSpecies;
