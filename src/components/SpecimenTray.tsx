import SpecimenCell from "@/components/SpecimenCell";
import {
  HERO_SPECIMENS,
  type FeaturedSpeciesItem,
} from "@/lib/featuredSpecies";
import { imageUrlById } from "@/lib/images";
import { speciesUrlFromName, toBinomialName } from "@/lib/names";

/**
 * The hero's unit tray: nine compartments of the day's featured specimens.
 *
 * Every state renders nine cells, so the tray is its full height from first
 * paint and the specimens settle in without moving the hero. On a phone the
 * last row is dropped and the tray is three rows of two.
 *
 * Pure markup, so it renders on the server and streams in with its data.
 */
export default function SpecimenTray({
  species,
}: {
  species: FeaturedSpeciesItem[] | null;
}) {
  return (
    <div className="rounded-3xl border border-deep-mocha-200 bg-white/70 p-2.5 shadow-[0_1px_2px_rgba(28,23,23,0.06),0_10px_28px_-14px_rgba(28,23,23,0.25)] backdrop-blur lg:rounded-r-none lg:border-r-0 dark:border-deep-mocha-700 dark:bg-deep-mocha-900/70 dark:shadow-[0_10px_28px_-14px_rgba(0,0,0,0.7)]">
      <ul
        className="m-0 grid list-none grid-cols-2 gap-px overflow-hidden rounded-2xl bg-deep-mocha-200 p-0 sm:grid-cols-3 dark:bg-deep-mocha-700"
        aria-label="Specimens from the collection"
      >
        {Array.from({ length: HERO_SPECIMENS }, (_, slot) => {
          const item = species?.[slot] ?? null;
          return (
            <li
              key={item?.slug ?? `slot-${slot}`}
              className={`flex ${slot >= 6 ? "max-sm:hidden" : ""}`}
            >
              <SpecimenCell
                href={item ? `/species/${speciesUrlFromName(item.slug)}` : null}
                imageUrl={item ? imageUrlById(item.imgId) : null}
                label={item ? toBinomialName(item.species) : ""}
                family={item?.family}
                alt={item ? `Specimen of ${toBinomialName(item.species)}` : ""}
                index={slot}
                settle
                sizes="(max-width: 640px) 45vw, (max-width: 1024px) 30vw, 17vw"
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
