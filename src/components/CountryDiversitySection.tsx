import LandingSectionHeading, {
  LANDING_CONTAINER,
} from "@/components/LandingSection";
import CountryDiversityPanel from "@/components/CountryDiversityPanel";
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
    <section
      className="w-full mt-20"
      aria-labelledby="country-diversity-heading"
    >
      <LandingSectionHeading
        id="country-diversity-heading"
        eyebrow="Distribution"
        title="Species diversity by country"
        description="Distinct species recorded in each country, from validated coordinates."
      />
      <div className={LANDING_CONTAINER}>
        <CountryDiversityPanel data={data} pending={pending} />
      </div>
    </section>
  );
}
