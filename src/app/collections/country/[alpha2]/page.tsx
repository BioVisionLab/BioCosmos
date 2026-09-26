import type { Metadata } from "next";
import { notFound } from "next/navigation";

import BackLink from "@/components/BackLink";
import { fetchCountrySpecies, isAlpha2 } from "@/lib/countryDiversity";
import CountrySpeciesTable from "./CountrySpeciesTable";

// Never pre-render at build time (API_HOST unavailable during Docker build)
export const dynamic = "force-dynamic";

type Params = Promise<{ alpha2: string }>;

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { alpha2 } = await params;
  const data = isAlpha2(alpha2) ? await fetchCountrySpecies(alpha2) : null;
  return {
    title: data ? `Species of ${data.countryName}` : "Country not found",
  };
}

export default async function CountrySpeciesPage({
  params,
}: {
  params: Params;
}) {
  const { alpha2 } = await params;
  if (!isAlpha2(alpha2)) notFound();
  const data = await fetchCountrySpecies(alpha2);
  // A code with no validated records is as absent here as an unknown one.
  if (!data) notFound();

  const images = data.species.reduce((sum, row) => sum + row.imageCount, 0);
  const imputed = data.species.reduce(
    (sum, row) => sum + row.imputedImageCount,
    0,
  );

  return (
    <main className="w-full max-w-5xl mx-auto py-8">
      <BackLink href="/collections/country" label="Back to Countries" />
      <h1 className="text-3xl font-bold mb-2">{data.countryName}</h1>
      <p className="mb-6 text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        <span className="font-mono">{data.countryCode}</span> ·{" "}
        {data.species.length.toLocaleString("en-US")} species ·{" "}
        {images.toLocaleString("en-US")} images
        {imputed > 0 &&
          ` (${imputed.toLocaleString("en-US")} with the country imputed from coordinates)`}
      </p>

      <CountrySpeciesTable rows={data.species} />
    </main>
  );
}
