import { LepTraitsAttribution } from "@/components/Attribution";
import { Affinity, FlightDuration, WingspanCard } from "./Traits";
import { LepTraits } from "@/lib/leptraits";
import { CanopyIcon } from "@/components/ui/Plants";

export function SpeciesDescription({
  traits,
  species,
}: {
  traits: LepTraits | null;
  species: string;
}) {
  return (
    <div className="mt-4 rounded-2xl bg-gradient-to-t from-emerald-500/5 to-transparent">
      <div className="bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-3 rounded-t-2xl">
        <h2 className="text-xl font-semibold mt-1 mb-1 ml-1">Key Traits</h2>
      </div>
      <div className="p-3">
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

  const showCanopy =
    typeof traits.canopy_affinity === "string" &&
    traits.canopy_affinity.trim() !== "";
  const keyTraitIconClass = "w-20 h-20 m-1 fill-teal-500";

  return (
    <section
      className="grid gap-1 md:grid-cols-2 transition-all p-1"
      aria-label="Key trait layout"
    >
      {/* Wingspan: shares row with Canopy Affinity when present, else spans full width */}
      <div className={`${boxClasses} ${showCanopy ? "" : "md:col-span-2"} h-fit`}>
        <h3 className="text-lg ml-2 mt-0 mb-2">Wingspan</h3>
        <div className="space-y-1">
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

      {/* Canopy Affinity: placed alongside Wingspan */}
      {showCanopy && (
        <div className={`${boxClasses} h-fit`}>
          <h3 className="text-lg ml-2 mt-0 mb-2">Canopy Affinity</h3>
          <Affinity
            affinity={traits.canopy_affinity!}
            icon={<CanopyIcon className={keyTraitIconClass} />}
          />
        </div>
      )}

      {/* Flight Duration: below, spanning full width */}
      {typeof traits.flight_duration === "number" &&
        !Number.isNaN(traits.flight_duration) && (
          <div className={`${boxClasses} md:col-span-2`}>
            <h3 className="text-lg ml-2 mt-0 mb-2">Flight Duration</h3>
            <FlightDuration
              duration={traits.flight_duration}
              iconClassName={keyTraitIconClass}
            />
          </div>
        )}
    </section>
  );
}
