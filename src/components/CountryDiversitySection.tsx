import LandingSectionHeading from "@/components/LandingSection";
import CountryDiversityPanel from "@/components/CountryDiversityPanel";
import { GlobeIcon } from "@/components/ui/icons";
import type { CountryDiversity } from "@/lib/countryDiversity";

/**
 * The landing-page section under the collection summary: where the
 * collection's species were recorded, by validated country.
 */
export default function CountryDiversitySection({
  data,
  pending = false,
}: {
  data: CountryDiversity | null;
  pending?: boolean;
}) {
  return (
    <section className="w-full mt-16" aria-labelledby="country-diversity-heading">
      <LandingSectionHeading
        id="country-diversity-heading"
        icon={<GlobeIcon />}
        title="Species Diversity by Country"
        description="Distinct species recorded in each country, from validated coordinates."
      />
      <div className="mx-auto max-w-5xl px-4">
        <CountryDiversityPanel data={data} pending={pending} />
      </div>
    </section>
  );
}
