import { SimilarSpeciesMeta } from "@/lib/speciesData";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { cleanSpeciesName } from "@/lib/names";

const IMAGE_SIZE = 128;

const labelColor = "text-gray-500 dark:text-gray-400";

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
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-200/50 dark:bg-gray-800/50 backdrop-blur">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
        <p className={`text-sm ${labelColor}`}>
          Found {meta.length} species similar to{" "}
          <span className="italic">{species}</span>.
        </p>
      </div>

      <SimilarSpeciesImageGallery
        speciesData={meta}
        label="Based on mean color and pattern similarity"
      />
    </div>
  );
}

function SimilarSpeciesImageGallery({
  speciesData,
  label,
}: {
  speciesData: SimilarSpeciesMeta[];
  label: string;
}) {
  return (
    <div className="p-4 mt-2">
      <h3 className={`text-md ${labelColor}`}>{label}</h3>
      <div className="overflow-x-auto rounded-xl flex flex-row gap-4 items-stretch">
        {speciesData.map((item, index) => (
          <SimilarSpeciesImage key={item.imgId} meta={item} index={index} />
        ))}
      </div>
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
      <div className="w-full item-center text-center">
        {thumbnailUrl ? (
          <><div className="h-full bg-gray-200 dark:bg-gray-700 rounded-2xl p-4">
            <Image
              src={thumbnailUrl}
              alt={`Similar species image ${meta.imgId}`}
              width={IMAGE_SIZE}
              height={IMAGE_SIZE}
              className="object-contain"
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
