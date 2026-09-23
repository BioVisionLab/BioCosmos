import { LANDING_GRID } from "@/components/LandingSection";
import { NoData } from "@/components/NoData";
import SpeciesTile from "@/components/SpeciesTile";
import { imageUrlById } from "@/lib/images";
import type { RepresentativeImage } from "@/lib/higherTaxa";
import { speciesHref } from "@/lib/taxonSlug";

/**
 * A strip of specimens from across a higher taxon, one species per tile.
 *
 * The tiles link to species pages rather than opening the specimen lightbox:
 * here the strip is a way into the group, and the collection details a
 * lightbox would show are what the species page's own specimen tab is for.
 * Keeping them as links also keeps this a server component.
 *
 * `LANDING_GRID` is not only for consistency with the landing page —
 * `SpeciesTile` carries a hard-coded `sizes` attribute that is correct for
 * that grid's breakpoints and no other.
 */
export default function TaxonImageStrip({
  images,
}: {
  images: RepresentativeImage[];
}) {
  if (images.length === 0) {
    return <NoData text="No specimen images for this group yet." />;
  }

  return (
    <ul className={`${LANDING_GRID} list-none m-0 p-0`}>
      {images.map((image) => (
        <li key={image.imageId}>
          <SpeciesTile
            href={speciesHref(image.species)}
            imageUrl={imageUrlById(image.imageId, "full")}
            label={image.displayName}
            alt={`Specimen of ${image.displayName}`}
          />
        </li>
      ))}
    </ul>
  );
}
