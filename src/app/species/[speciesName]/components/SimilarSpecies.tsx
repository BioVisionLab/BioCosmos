import { SimilarSpeciesMeta } from "@/lib/speciesData";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import { cleanSpeciesName } from "@/lib/names";

const IMAGE_SIZE = 128;

const labelColor = "text-gray-500 dark:text-gray-400";

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

  return (
    <div className="mt-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-200/50 dark:bg-gray-800/50 backdrop-blur">
      <div className="border-b border-gray-300 dark:border-gray-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
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
      </div>
    </div>
  );
}

export default VisuallySimilarSpecies;
