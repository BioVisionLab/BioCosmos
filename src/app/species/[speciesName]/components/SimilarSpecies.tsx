"use client";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { cleanSpeciesName } from "@/lib/names";
import { SimilarSpeciesList, SimilarSpeciesMeta } from "@/lib/similarSpecies";

const IMAGE_SIZE = 120;

const labelColor = "text-gray-500 dark:text-gray-400";

<<<<<<< HEAD
// Fetch all thumbnails in bulk and show placeholders until all are available.
function VisuallySimilarSpecies({
  species,
  meta,
}: {
  species: string;
  meta: SimilarSpeciesMeta[];
}) {
  const [thumbs, setThumbs] = useState<(string | null)[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!meta || meta.length === 0) return;
    let mounted = true;
    const loadAll = async () => {
      setLoading(true);
      try {
        const results = await Promise.all(
          meta.map(async (m) => {
            try {
              const url = await fetchThumbnailById(m.imgId);
              return url;
            } catch (e) {
              return null;
            }
          })
        );
        if (!mounted) return;
        setThumbs(results);
      } catch (err) {
        console.error("Failed to load similar species thumbnails:", err);
        if (mounted) setThumbs(meta.map(() => null));
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadAll();
    return () => {
      mounted = false;
    };
  }, [meta]);

  if (!meta || meta.length === 0) return null;

=======
function VisuallySimilarSpecies({ species }: { species: string }) {
  const [similarSpecies, setSimilarSpecies] =
    useState<SimilarSpeciesList | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchSimilarSpecies = async () => {
      // We add a small delay to avoid this expensive call happening too quickly
      // after the main species data fetch.
      await new Promise((resolve) => setTimeout(resolve, 500));
      try {
        const response = await fetch(
          `/api/ml-search/similarity?species=${encodeURIComponent(species)}`
        );
        if (!response.ok) {
          console.error(
            `Failed to fetch similar species for ${species}: ${response.statusText}`
          );
          setIsLoading(false);
          return;
        }
        const data: SimilarSpeciesList = await response.json();
        setSimilarSpecies(data);
      } catch (error) {
        console.error("Error fetching similar species:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchSimilarSpecies();
  }, [species]);

  const isNotFound =
    !similarSpecies ||
    (similarSpecies.dorsal.length === 0 && similarSpecies.ventral.length === 0);
>>>>>>> api-redesign
  return (
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-200/50 dark:bg-gray-800/50 backdrop-blur">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
<<<<<<< HEAD
        <p className={`text-sm ${labelColor}`}>
          Found {meta.length} species similar to <span className="italic">{species}</span>.
        </p>
      </div>

      <div className="p-4 mt-2">
        <h3 className={`text-md ${labelColor}`}>Based on mean color and pattern similarity</h3>
        <div className="overflow-x-auto rounded-xl flex flex-row gap-4 mt-2">
          {thumbs === null || loading
            ? // show placeholders until all thumbnails are fetched
              meta.map((_, i) => (
                <div key={`ph-${i}`} className="w-[128px] h-[128px] bg-gray-300 dark:bg-gray-700 rounded-lg flex items-center justify-center">
                  <ImageLoading size={IMAGE_SIZE} />
                </div>
              ))
            : meta.map((item, index) => {
                const url = thumbs[index];
                const speciesName = cleanSpeciesName(item.species);
                return (
                  <Link key={item.imgId} href={`/species/${item.species}`}>
                    <div className="item-center text-center w-[128px]">
                      {url ? (
                        <>
                          <Image src={url} alt={`Similar species image ${item.imgId}`} width={IMAGE_SIZE} height={IMAGE_SIZE} className="object-fill mx-auto" />
                          <p className="text-sm text-gray-500 dark:text-gray-400 italic">{speciesName}</p>
                        </>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-800 rounded">
                          <ImageLoading size={IMAGE_SIZE} />
                        </div>
                      )}
                    </div>
                  </Link>
                );
              })}
        </div>
=======
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Other species that look similar to <i>{species}</i> based on image
          embedding similarity.
        </p>
      </div>
      {isLoading ? (
        <div className="p-4">
          <ImageLoading
            size={IMAGE_SIZE}
            msg="Searching for visually similar species"
          />
        </div>
      ) : isNotFound ? (
        <div className="p-4 text-sm text-center text-gray-500 dark:text-gray-400">
          No visually similar species found.
        </div>
      ) : (
        <div>
          {/* <SimilarSpeciesImageGallery
            speciesData={similarSpecies.anySides}
            label="Overall Similarity"
          /> */}
          <SimilarSpeciesImageGallery
            speciesData={similarSpecies.dorsal}
            label="Dorsal"
          />
          <SimilarSpeciesImageGallery
            speciesData={similarSpecies.ventral}
            label="Ventral"
          />
        </div>
      )}
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
  if (speciesData.length === 0) {
    return null;
  }
  return (
    <div className="p-2 ml-4">
      <h3 className={`text-md ${labelColor}`}>{label}</h3>
      <div className="overflow-x-auto flex flex-row gap-4 mt-2">
        {speciesData.map((item, index) => (
          <SimilarSpeciesImage key={item.imgId} meta={item} index={index} />
        ))}
>>>>>>> api-redesign
      </div>
    </div>
  );
}

<<<<<<< HEAD
=======
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
      <div className="h-full rounded-xl items-center justify-center flex-shrink-0 mb-2">
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
            <p className="text-sm text-center w-[120px] text-gray-500 dark:text-gray-400 italic break-words whitespace-normal">
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

>>>>>>> api-redesign
export default VisuallySimilarSpecies;
