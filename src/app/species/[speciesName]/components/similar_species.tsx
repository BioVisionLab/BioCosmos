import { SimilarSpeciesMeta } from "@/lib/speciesData";
import { fetchSimilarImg } from "@/lib/speciesList";
import Image from "next/image";
import { useEffect, useState } from "react";

function SimilarSpecies({
  species,
  meta,
}: {
  species: string;
  meta: SimilarSpeciesMeta[];
}) {
  if (meta.length === 0) {
    return null; // Don't render anything if there are no similar species
  }
  return (
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-white/70 dark:bg-gray-800/70 backdrop-blur shadow">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Similar species to <span className="italic">{species}</span> based on
          image analysis.
        </p>
      </div>

      <SimilarSpeciesImageGallery meta={meta} />
    </div>
  );
}

function SimilarSpeciesImageGallery({ meta }: { meta: SimilarSpeciesMeta[] }) {
  return (
    <div className="overflow-x-auto rounded-xl px-2">
      {meta.map((item) => (
        <div key={item.imgId}>
          <SimilarSpeciesImage meta={item} />
        </div>
      ))}
    </div>
  );
}

function SimilarSpeciesImage({ meta }: { meta: SimilarSpeciesMeta }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchImage = async () => {
      try {
        const response = await fetchSimilarImg(meta.imgId);
        setImageUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      }
    };
    fetchImage();
  }, [meta.imgId]);

  return (
    imageUrl && (
      <div className="inline-block m-4 text-center">
        <div className="relative w-32 h-32 inline-block overflow-hidden">
          <Image
            src={imageUrl}
            alt={`Similar species image ${meta.imgId}`}
            fill
            className="object-fill"
          />
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">
          {meta.species}
        </p>
      </div>
    )
  );
}

export default SimilarSpecies;
