import LandingSectionHeading, {
  LANDING_CONTAINER,
} from "@/components/LandingSection";
import SpecimenCell from "@/components/SpecimenCell";
import type { TaxonNode } from "@/lib/higherTaxa";
import { imageUrlById } from "@/lib/images";

// The tray is laid out six, three or two to a row. Padding it to a multiple
// of six closes the last row at every one of those widths, so the tray never
// ends on a ragged edge — the spare compartments stay empty, as they would in
// a drawer.
const ROW_MULTIPLE = 6;

/**
 * One specimen for each family the collection holds, each leading to that
 * family's page.
 *
 * Drawn as the same tray as "Explore by appearance" directly above it, so
 * the two read as a pair: one way in by what a butterfly looks like, one by
 * where it sits in the classification.
 *
 * A server component. The families and their images come from the order
 * payload, which is cached for thirty days alongside the order page.
 *
 * @param families Null while pending or when the order could not be loaded;
 *   the tray then shows one row of empty compartments at the same height.
 */
export default function FamilyExplorer({
  families,
}: {
  families: TaxonNode[] | null;
}) {
  const count = families?.length ?? 0;
  const slots = Math.max(
    ROW_MULTIPLE,
    Math.ceil(count / ROW_MULTIPLE) * ROW_MULTIPLE,
  );

  return (
    <section className="w-full mt-20" aria-labelledby="family-explorer-heading">
      <LandingSectionHeading
        id="family-explorer-heading"
        eyebrow="Taxonomy"
        title="Explore by family"
        description="Each family is shown by its most-photographed species. Open one to browse its genera and species."
      />

      <div className={LANDING_CONTAINER}>
        <ul
          aria-busy={families === null}
          className="bc-reveal m-0 grid list-none grid-cols-2 gap-px overflow-hidden rounded-2xl border border-deep-mocha-200 bg-deep-mocha-200 p-0 sm:grid-cols-3 lg:grid-cols-6 dark:border-deep-mocha-700 dark:bg-deep-mocha-700"
        >
          {Array.from({ length: slots }, (_, slot) => {
            const family = families?.[slot] ?? null;
            // An empty compartment is decoration, not a list item a screen
            // reader should count.
            if (!family) {
              return (
                <li key={`slot-${slot}`} className="flex" aria-hidden="true">
                  <SpecimenCell
                    href={null}
                    imageUrl={null}
                    label=""
                    alt=""
                    index={slot}
                  />
                </li>
              );
            }
            return (
              <li key={family.key} className="flex">
                <SpecimenCell
                  href={family.href}
                  imageUrl={
                    family.imageId ? imageUrlById(family.imageId, "full") : null
                  }
                  label={family.name}
                  italic={false}
                  family={`${family.speciesCount.toLocaleString()} species`}
                  alt={
                    family.imageName
                      ? `${family.imageName}, representing ${family.name}`
                      : family.name
                  }
                  index={slot}
                  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 17vw"
                />
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
