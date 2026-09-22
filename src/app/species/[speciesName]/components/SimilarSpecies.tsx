"use client";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import {
  cleanSpeciesName,
  isSpeciesName,
  isSubspeciesName,
  speciesUrlFromName,
  toBinomialName,
} from "@/lib/names";
import {
  fetchSimilarSpecies,
  SimilarSpeciesList,
  SimilarSpeciesMeta,
} from "@/lib/similarSpecies";
import { useInView } from "@/lib/useInView";

const IMAGE_SIZE = 120;

const labelColor = "text-deep-mocha-500 dark:text-deep-mocha-400";

function VisuallySimilarSpecies({ species }: { species: string }) {
  const [similarSpecies, setSimilarSpecies] =
    useState<SimilarSpeciesList | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const { ref, inView } = useInView<HTMLDivElement>();

  useEffect(() => {
    if (!species) {
      setIsLoading(false);
      setSimilarSpecies(null);
      return;
    }
    // This embedding search is expensive and the panel sits below the fold, so
    // hold off until the reader actually scrolls towards it.
    if (!inView) return;

    // Aborted on cleanup, and the result dropped on the way back in. This is
    // the slowest request the species page makes, so without it a response for
    // the species a reader just navigated away from can land after the next
    // one and overwrite the panel with the wrong neighbours.
    const controller = new AbortController();
    let ignore = false;

    const load = async () => {
      try {
        const data = await fetchSimilarSpecies(species, controller.signal);
        if (ignore) return;
        setSimilarSpecies(data);
      } catch (error) {
        // The only throw the helper lets through is the abort, which means a
        // newer request has already taken over. Leave the panel alone.
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        console.error("Error fetching similar species:", error);
      } finally {
        if (!ignore) setIsLoading(false);
      }
    };
    load();

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [species, inView]);

  const isNotFound =
    !similarSpecies ||
    (similarSpecies.dorsal.length === 0 && similarSpecies.ventral.length === 0);
  return (
    <div
      ref={ref}
      className="mt-4 border border-deep-mocha-300 dark:border-deep-mocha-600 rounded-xl bg-deep-mocha-200/50 dark:bg-deep-mocha-800/50 backdrop-blur"
    >
      <div className="border-b border-deep-mocha-300 dark:border-deep-mocha-600 p-4">
        <h2 className="text-2xl font-semibold">Visually Similar Species</h2>
        <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
          Other species that look similar to{" "}
          {/* `species` is the URL slug, so it needs un-slugging before it is
              shown as prose. */}
          <i>{toBinomialName(cleanSpeciesName(species))}</i> based on image
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
        <div className="p-4 text-sm text-center text-deep-mocha-500 dark:text-deep-mocha-400">
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
    // Up to twenty of these mount at once, one per neighbour, and each one
    // outlives its card if the reader scrolls on. Latched so a late thumbnail
    // cannot set state on a card that has already been replaced.
    let ignore = false;
    const fetchImage = async () => {
      try {
        const response = await fetchThumbnailById(meta.imgId);
        if (!ignore) setThumbnailUrl(response);
      } catch (error) {
        console.error("Error fetching similar species image:", error);
      }
    };
    fetchImage();
    return () => {
      ignore = true;
    };
  }, [meta.imgId]);

  // The accepted species name is what a reader compares against, so it is the
  // only name shown — unless the record is a subspecies, which is genuinely
  // more specific than the binomial above it and worth naming. A record that
  // differs for any other reason, a misspelling or a synonym, says nothing
  // extra: the accepted name has already answered the question.
  //
  // The link still targets the recorded slug, because that is what the
  // gallery endpoints key on.
  const recordedName = toBinomialName(cleanSpeciesName(meta.species));
  const acceptedName = meta.acceptedName
    ? toBinomialName(meta.acceptedName)
    : null;
  const showsSubspecies =
    isSubspeciesName(meta.species) &&
    !!acceptedName &&
    acceptedName.toLowerCase() !== recordedName.toLowerCase();

  const card = (
    <div className="h-full rounded-xl items-center justify-center flex-shrink-0 mb-2">
      {thumbnailUrl ? (
        <>
          <div className="flex w-[120px] h-[120px] relative my-auto bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-xl p-2 items-center justify-center">
            <Image
              src={thumbnailUrl}
              alt={`Similar species image ${meta.imgId}`}
              width={IMAGE_SIZE}
              height={IMAGE_SIZE}
              className="object-contain"
              unoptimized
            />
          </div>
          <div className="w-[120px] text-center">
            <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400 italic break-words whitespace-normal">
              {acceptedName ?? recordedName}
            </p>
            {showsSubspecies ? (
              <p className="text-xs text-deep-mocha-400 dark:text-deep-mocha-500 italic break-words whitespace-normal">
                as {recordedName}
              </p>
            ) : null}
          </div>
        </>
      ) : (
        <ImageLoading size={IMAGE_SIZE} />
      )}
    </div>
  );

  // The backend drops genus-only matches from this panel, so the plain branch
  // is a guard rather than something a reader should meet — but an older
  // precomputed table predates that filter, and a card leading to an empty
  // gallery is worse than a card leading nowhere.
  if (!isSpeciesName(meta.species)) return card;

  return (
    <Link key={index} href={`/species/${speciesUrlFromName(meta.species)}`}>
      {card}
    </Link>
  );
}

export default VisuallySimilarSpecies;
