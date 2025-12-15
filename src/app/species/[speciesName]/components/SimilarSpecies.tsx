import { SimilarSpeciesMeta } from "@/lib/speciesData";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { cleanSpeciesName } from "@/lib/names";

const IMAGE_SIZE = 120;

const labelColor = "text-gray-500 dark:text-gray-400";

function VisuallySimilarSpecies({ species }: { species: string }) {
  const [similarSpecies, setSimilarSpecies] = useState<SimilarSpeciesMeta[]>(
    []
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchSimilarSpecies = async () => {
      try {
        // const response = [];
        // if (!response.ok) {
        //   console.error(
        //     `Failed to fetch similar species for ${species}: ${response.statusText}`
        //   );
        //   setIsLoading(false);
        //   return;
        // }
        const data: SimilarSpeciesMeta[] = [];
        setSimilarSpecies(data);
      } catch (error) {
        console.error("Error fetching similar species:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchSimilarSpecies();
  }, [species]);

  if (isLoading) {
    return (
      <div className="mt-4 p-4">
        <p className={labelColor}>Loading visually similar species...</p>
      </div>
    );
  }
  if (similarSpecies.length === 0) {
    return null; // Don't render anything if there are no similar species
  }
  return (
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-200/50 dark:bg-gray-800/50 backdrop-blur">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
        <p className={`text-sm ${labelColor}`}>
          Found {similarSpecies.length} species similar to{" "}
          <span className="italic">{species}</span>.
        </p>
      </div>

      <SimilarSpeciesImageGallery
        speciesData={similarSpecies}
        label="Mean color and pattern similarity"
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
      <div className="overflow-x-auto flex flex-row gap-4 items-stretch mt-2">
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
      <div className="h-full rounded-xl items-center justify-center flex-shrink-0 mb-4">
        {thumbnailUrl ? (
          <>
            <div className="flex w-[120px] h-[120px] relative my-auto bg-gray-200 dark:bg-gray-700 rounded-xl p-2 items-center justify-center">
              <Image
                src={thumbnailUrl}
                alt={`Similar species image ${meta.imgId}`}
                width={IMAGE_SIZE}
                height={IMAGE_SIZE}
                className="object-contain"
              />
            </div>
            <p className="text-sm text-center text-gray-500 dark:text-gray-400 italic">
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
