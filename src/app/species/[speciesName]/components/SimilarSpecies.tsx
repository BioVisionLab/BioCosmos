"use client";
import { fetchThumbnailById } from "@/lib/images";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ImageLoading } from "@/components/Loadings";
import NoImage from "@/components/NoImage";
import {
  cleanSpeciesName,
  isSubspeciesName,
  toBinomialName,
} from "@/lib/names";
import {
  fetchSimilarSpecies,
  SimilarSpeciesMeta,
  SimilarSpeciesSide,
} from "@/lib/similarSpecies";
import { speciesHref, speciesPageHref } from "@/lib/taxonSlug";
import { useInView } from "@/lib/useInView";

const IMAGE_SIZE = 120;

const labelColor = "text-deep-mocha-500 dark:text-deep-mocha-400";

/**
 * The visually-similar panel, one section per wing surface.
 *
 * Dorsal and ventral are two separate searches on the backend and always were,
 * so fetching them in one request only meant the faster one waited on the
 * slower. Behind a single loading flag that turned the whole panel into an
 * empty tinted box with one spinner in it for as long as the slowest search
 * took -- up to the proxy's fifteen second deadline.
 *
 * Each section now owns its request, so it paints when its own answer lands,
 * and both headings are on screen from the first frame: the reader can see
 * what is coming rather than watching one undifferentiated block.
 *
 * `useInView` stays on the panel, not on the sections. The two are always in
 * view together, so one observer says everything two would.
 */
function VisuallySimilarSpecies({ species }: { species: string }) {
  const [emptySides, setEmptySides] = useState<Record<string, boolean>>({});
  const { ref, inView } = useInView<HTMLDivElement>();

  // Only once both sections have finished and found nothing is the panel
  // genuinely empty. Saying so while one is still searching would be wrong.
  const isNotFound = emptySides.dorsal === true && emptySides.ventral === true;

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
      {isNotFound ? (
        <div className="p-4 text-sm text-center text-deep-mocha-500 dark:text-deep-mocha-400">
          No visually similar species found.
        </div>
      ) : (
        <div>
          <SimilarSpeciesSection
            species={species}
            side="dorsal"
            label="Dorsal"
            inView={inView}
            onSettled={(isEmpty) =>
              setEmptySides((prev) => ({ ...prev, dorsal: isEmpty }))
            }
          />
          <SimilarSpeciesSection
            species={species}
            side="ventral"
            label="Ventral"
            inView={inView}
            onSettled={(isEmpty) =>
              setEmptySides((prev) => ({ ...prev, ventral: isEmpty }))
            }
          />
        </div>
      )}
    </div>
  );
}

/**
 * One wing surface: its own request, its own loading state.
 *
 * The row keeps a fixed height while it loads so the panel does not jump as
 * each side lands.
 */
function SimilarSpeciesSection({
  species,
  side,
  label,
  inView,
  onSettled,
}: {
  species: string;
  side: SimilarSpeciesSide;
  label: string;
  inView: boolean;
  onSettled: (isEmpty: boolean) => void;
}) {
  const [rows, setRows] = useState<SimilarSpeciesMeta[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!species) {
      setIsLoading(false);
      setRows(null);
      return;
    }
    // This embedding search is expensive and the panel sits below the fold, so
    // hold off until the reader actually scrolls towards it.
    if (!inView) return;

    // Aborted on cleanup, and the result dropped on the way back in. This is
    // the slowest request the species page makes, so without it a response for
    // the species a reader just navigated away from can land after the next
    // one and overwrite the panel with the wrong neighbours. Each section
    // needs its own controller now that they resolve independently.
    const controller = new AbortController();
    let ignore = false;

    setIsLoading(true);
    const load = async () => {
      try {
        const data = await fetchSimilarSpecies(
          species,
          side,
          controller.signal
        );
        if (ignore) return;
        setRows(data ? data[side] : []);
      } catch (error) {
        // The only throw the helper lets through is the abort, which means a
        // newer request has already taken over. Leave the section alone.
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        console.error(`Error fetching ${side} similar species:`, error);
        if (!ignore) setRows([]);
      } finally {
        if (!ignore) setIsLoading(false);
      }
    };
    load();

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [species, side, inView]);

  // Report upward only once this section has actually settled, so the panel
  // cannot show "nothing found" while the other side is still searching.
  useEffect(() => {
    if (!isLoading && rows !== null) onSettled(rows.length === 0);
    // `onSettled` is a fresh closure each render; depending on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, rows]);

  if (!isLoading && rows !== null && rows.length === 0) {
    return null;
  }

  return (
    <div className="p-2 ml-4">
      <h3 className={`text-md ${labelColor}`}>{label}</h3>
      <div
        className="overflow-x-auto flex flex-row gap-4 mt-2 pb-2 items-stretch"
        style={{ minHeight: IMAGE_SIZE + 76 }}
      >
        {isLoading || rows === null ? (
          <div className="flex items-center" style={{ height: IMAGE_SIZE }}>
            <ImageLoading
              size={IMAGE_SIZE}
              msg={`Searching ${label.toLowerCase()} matches`}
            />
          </div>
        ) : (
          rows.map((item, index) => (
            <SimilarSpeciesImage key={item.imgId} meta={item} index={index} />
          ))
        )}
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
  // `fetchThumbnailById` only builds a URL -- it does no I/O -- so the moment
  // it resolves the tile has a src and nothing else. Tracking the image's own
  // load event is what stops the card sitting there as a bare tinted square
  // for the whole time the bytes are actually in flight.
  const [isImageReady, setIsImageReady] = useState(false);
  const [isImageFailed, setIsImageFailed] = useState(false);

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
        if (!ignore) {
          setIsImageReady(true);
          setIsImageFailed(true);
        }
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

  // Laid out like the ML search result card: one panel holding the image
  // well and, under it, the name.
  const card = (
    <div className="flex w-[152px] flex-shrink-0 flex-col items-center gap-2 rounded-2xl bg-deep-mocha-200 dark:bg-deep-mocha-700 p-4 text-center shadow-sm transition-shadow hover:shadow-md">
      <div className="relative w-full aspect-square">
        {thumbnailUrl && !isImageFailed ? (
          <Image
            src={thumbnailUrl}
            alt={`Similar species image ${meta.imgId}`}
            fill
            sizes={`${IMAGE_SIZE}px`}
            className={`object-contain transition-opacity duration-200 ${
              isImageReady ? "opacity-100" : "opacity-0"
            }`}
            onLoad={() => setIsImageReady(true)}
            onError={() => {
              setIsImageReady(true);
              setIsImageFailed(true);
            }}
            unoptimized
          />
        ) : null}
        {isImageFailed ? <NoImage /> : null}
        {isImageReady ? null : (
          <div className="absolute inset-0 flex items-center justify-center">
            <ImageLoading size={IMAGE_SIZE / 2} msg="" />
          </div>
        )}
      </div>
      <div className="w-full">
        <p className="text-sm italic break-words text-deep-mocha-800 dark:text-deep-mocha-100">
          {acceptedName ?? recordedName}
        </p>
        {showsSubspecies ? (
          <p className="text-xs italic break-words text-deep-mocha-500 dark:text-deep-mocha-400">
            as {recordedName}
          </p>
        ) : null}
      </div>
    </div>
  );

  // The backend drops any match with no species page from this panel, so
  // the plain branch is a guard rather than something a reader should meet —
  // but a card leading to an orphaned page is worse than one leading nowhere.
  //
  // The key can also be missing outright: this response is CDN-cached for a
  // day, so a payload from a backend that predates `speciesKey` keeps being
  // served after a deploy. Every card was then a dead end. A missing key
  // falls back to the recorded name, which is what these links used before.
  const href =
    meta.speciesKey === undefined
      ? speciesHref(meta.species)
      : speciesPageHref(meta.speciesKey);
  if (!href) return card;

  return (
    <Link key={index} href={href} className="flex">
      {card}
    </Link>
  );
}

export default VisuallySimilarSpecies;
