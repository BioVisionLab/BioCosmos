import { redirect } from "next/navigation";

import { NoData } from "@/components/NoData";
import SpeciesTile from "@/components/SpeciesTile";
import { SPECIES_GRID, SPECIES_GRID_SIZES } from "@/components/speciesGrid";
import TaxonSpeciesPager from "@/components/TaxonSpeciesPager";
import { type HigherRank, fetchHigherTaxonSpecies } from "@/lib/higherTaxa";
import { imageUrlById } from "@/lib/images";
import { speciesHref } from "@/lib/taxonSlug";

/** The page a `?page=` value names; anything unreadable is the first. */
export function parseSpeciesPage(value: string | string[] | undefined): number {
  const page = Number.parseInt(Array.isArray(value) ? value[0] : (value ?? ""));

  return Number.isFinite(page) && page >= 1 ? page : 1;
}

/**
 * Every species of a higher taxon with images, a page at a time, laid out
 * like the species results of a text search.
 *
 * `href` is the taxon's own URL, where a page past the last one is sent back
 * to the last.
 */
export default async function TaxonSpeciesList({
  rank,
  taxonKey,
  page,
  href,
  title,
  headingId,
}: {
  rank: HigherRank;
  /** The overview's key, which names the taxon to the species endpoint. */
  taxonKey: string;
  page: number;
  href: string | null;
  /** The heading, to which the species count is added as on the search. */
  title: string;
  headingId: string;
}) {
  const result = await fetchHigherTaxonSpecies(rank, taxonKey, page);
  const total = result?.total ?? 0;
  const heading = (
    <h2 id={headingId} className="text-2xl font-semibold mb-3">
      {title}
      {total > 0 ? ` (${total.toLocaleString()})` : null}
    </h2>
  );

  if (!result || total === 0) {
    return (
      <>
        {heading}
        <NoData text="No specimen images for this group yet." />
      </>
    );
  }

  const totalPages = Math.ceil(total / result.limit);

  if (page > totalPages && href) redirect(`${href}?page=${totalPages}`);

  return (
    <TaxonSpeciesPager
      heading={heading}
      page={Math.min(page, totalPages)}
      totalPages={totalPages}
      total={total}
      perPage={result.limit}
    >
      <ul className={`${SPECIES_GRID} list-none m-0 p-0`}>
        {result.species.map((image) => (
          <li key={image.imageId}>
            <SpeciesTile
              href={speciesHref(image.species)}
              imageUrl={imageUrlById(image.imageId, "full")}
              label={image.displayName}
              alt={`Specimen of ${image.displayName}`}
              sizes={SPECIES_GRID_SIZES}
            />
          </li>
        ))}
      </ul>
    </TaxonSpeciesPager>
  );
}
