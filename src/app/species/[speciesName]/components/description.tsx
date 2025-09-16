import { LepTraitsAttribution } from "@/components/Attribution";
import { LepTraits } from "@/lib/speciesData";
import { CanopyAffinity, FlightDuration, WingspanCard } from "./Traits";

export function SpeciesDescription({
  traits,
  species,
}: {
  traits: LepTraits | null;
  species: string;
}) {
  return (
    <div className="mt-8 rounded-2xl bg-gradient-to-t from-emerald-500/5 to-transparent">
      <div className="bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-4 rounded-t-2xl">
        <h2 className="text-2xl font-semibold">Key Traits</h2>
      </div>
      <div className="p-4">
        <SpeciesDescriptionText traits={traits} species={species} />
        <LepTraitsAttribution />
      </div>
    </div>
  );
}

function SpeciesDescriptionText({
  traits,
  species,
}: {
  traits: LepTraits | null;
  species: string;
}) {
  if (!traits) {
    return (
      <p className="text-gray-500 dark:text-gray-400 mt-2">
        No traits available for <i>{species}</i>.
      </p>
    );
  }
  const containerClasses = "my-4 relative rounded-xl p-2 overflow-hidden";
  const boxClasses = containerClasses.replace("my-4", ""); // remove outer margin for grid layout

  return (
    <section
      className="grid gap-2 md:grid-cols-2 transition-all p-2"
      aria-label="Key trait layout"
    >
      {/* Wingspan spans two rows on md+ to avoid wrapper gaps */}
      <div className={`${boxClasses} md:col-span-2 h-fit`}>
        <h3 className="text-xl m-2">Wingspan</h3>
        <div className="space-y-2">
          <WingspanCard
            upper_male={traits.wingspan_upper_male}
            upper_female={traits.wingspan_upper_female}
            upper_unspecified={traits.wingspan_upper_unspecified}
            lower_male={traits.wingspan_lower_male}
            lower_female={traits.wingspan_lower_female}
            lower_unspecified={traits.wingspan_lower_unspecified}
          />
        </div>
      </div>

      {/* Each small card is its own grid item (no wrapping flex) */}
      {typeof traits.flight_duration === "number" &&
        !Number.isNaN(traits.flight_duration) && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Flight Duration</h3>
            <FlightDuration duration={traits.flight_duration} />
          </div>
        )}

      {typeof traits.canopy_affinity === "string" &&
        traits.canopy_affinity.trim() !== "" && (
          <div className={boxClasses}>
            <h3 className="text-xl m-2">Canopy Affinity</h3>
            <CanopyAffinity affinity={traits.canopy_affinity} />
          </div>
        )}
    </section>
  );
}
