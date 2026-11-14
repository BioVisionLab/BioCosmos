import type { Metadata } from "next";

import { NoData } from "@/components/NoData";
import TaxonBreadcrumb, { type Crumb } from "@/components/TaxonBreadcrumb";
import { cleanSpeciesName, isSpeciesName } from "@/lib/names";
import { parseSpeciesSlug } from "@/lib/speciesData";
import { fetchGalleryImageIds, fetchSpeciesData } from "@/lib/speciesPage";
import { familyHref, genusHref } from "@/lib/taxonSlug";

import TabsComponent from "./components/PageTabs";
import SpeciesHeader from "./components/SpeciesTitle";

// Never pre-rendered at build time: API_HOST is unavailable during the Docker
// build. The day-long cache lives on the fetches in @/lib/speciesPage, which
// survive the no-store default this flag sets.
export const dynamic = "force-dynamic";

interface SpeciesPageProps {
  params: Promise<{ speciesName: string }>;
}

export async function generateMetadata({
  params,
}: SpeciesPageProps): Promise<Metadata> {
  const { speciesName } = await params;

  if (!isSpeciesName(speciesName)) return { title: "Not a species name" };

  const { formattedName } = parseSpeciesSlug(speciesName);
  const { taxonomy } = await fetchSpeciesData(speciesName);
  const name = taxonomy?.species ?? formattedName;
  const family = taxonomy?.family ? ` in the family ${taxonomy.family}` : "";
  const common = taxonomy?.vernacularName
    ? ` (${taxonomy.vernacularName})`
    : "";

  return {
    title: name,
    description:
      `${name}${common}, a butterfly${family}: specimen images, ` +
      `classification, traits, distribution and literature.`,
  };
}

export default async function SpeciesPage({ params }: SpeciesPageProps) {
  const { speciesName } = await params;

  // A species page is a page about a species. A slug that names only a
  // genus, or is otherwise not a binomial, has no images to show and no
  // classification to resolve, so say so without asking the backend.
  if (!isSpeciesName(speciesName)) {
    return (
      <div className="m-2 ">
        <NoData
          text={`"${cleanSpeciesName(speciesName)}" is not a species name. Species pages need a genus and a specific epithet.`}
        />
      </div>
    );
  }

  // Both at once: the gallery's first image is the page's Largest
  // Contentful Paint, and its ids should not wait behind the classification.
  const [speciesData, galleryImageIds] = await Promise.all([
    fetchSpeciesData(speciesName),
    fetchGalleryImageIds(speciesName),
  ]);
  const { genus, formattedName } = parseSpeciesSlug(speciesName);
  const family = speciesData.taxonomy?.family;
  const name = speciesData.taxonomy?.species ?? formattedName;
  const crumbs: Crumb[] = [{ label: "Home", href: "/" }];

  if (family) crumbs.push({ label: family, href: familyHref(family) });

  crumbs.push({ label: genus, href: genusHref(genus), italic: true });
  crumbs.push({ label: name, italic: true });

  return (
    <div className="m-2 ">
      <section>
        <TaxonBreadcrumb items={crumbs} />

        <div>
          <SpeciesHeader taxonomy={speciesData.taxonomy} name={name} />

          <div className="mt-8">
            <TabsComponent
              speciesData={speciesData}
              speciesSlug={speciesName}
              galleryImageIds={galleryImageIds}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
