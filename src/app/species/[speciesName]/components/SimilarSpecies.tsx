import { SimilarSpeciesMeta } from "@/lib/speciesData";
import { fetchThumbnailById } from "@/lib/speciesList";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import ImageLoading from "@/components/ImageLoading";
import { cleanSpeciesName } from "@/lib/names";

const IMAGE_SIZE = 128;

function VisuallySimilarSpecies({
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
          Found {meta.length} species similar to{" "}
          <span className="italic">{species}</span>.
        </p>
      </div>

      <SimilarSpeciesImageGallery meta={meta} />
    </div>
  );
}

function SimilarSpeciesImageGallery({ meta }: { meta: SimilarSpeciesMeta[] }) {
  return (
    <div className="overflow-x-auto rounded-xl px-2 flex flex-row gap-4 py-2">
      {meta.map((item, index) => (
        <SimilarSpeciesImage key={item.imgId} meta={item} index={index} />
      ))}
    </div>
  );
}

function SimilarSpeciesImage({
  meta,
  index,
}: {
  meta: SimilarSpeciesMeta;
  index: number;
}) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(meta.imgId);
        setThumbnailUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      }
    };
    fetchImage();
  }, [meta.imgId]);

  const speciesName = cleanSpeciesName(meta.species);

  return (
    <Link key={index} href={`/species/${meta.species}`}>
      <div className="inline-block m-4 text-center">
        {thumbnailUrl ? (
          <>
            <div className="relative w-32 h-32 inline-block overflow-hidden">
              <Image
                src={thumbnailUrl}
                alt={`Similar species image ${meta.imgId}`}
                width={IMAGE_SIZE}
                height={IMAGE_SIZE}
                className="object-fill mx-auto"
              />
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              {speciesName}
            </p>
          </>
        ) : (
          <ImageLoading size={IMAGE_SIZE} />
        )}
      </div>
    </Link>
  );
}

export default VisuallySimilarSpecies;
