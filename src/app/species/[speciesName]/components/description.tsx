import { LepTraitsAttribution } from "@/components/Attribution";
import { LepTraits } from "@/lib/speciesData";
import { Plane, Target, Trees } from "lucide-react";

const valueClass =
  "font-semibold text-emerald-600 dark:text-emerald-300 text-xl";

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

function WingspanCard({
  upper_male,
  upper_female,
  upper_unspecified,
  lower_male,
  lower_female,
  lower_unspecified,
}: {
  upper_male: number | null | undefined;
  upper_female: number | null | undefined;
  upper_unspecified: number | null | undefined;
  lower_male: number | null | undefined;
  lower_female: number | null | undefined;
  lower_unspecified: number | null | undefined;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Target className="h-32 w-32" />
      </div>
      <div className="space-y-2 ml-4">
        <div>
          <h3 className="text-lg leading-tight">Upper</h3>
          {upper_male || upper_female || upper_unspecified ? (
            <Wingspan
              male={upper_male}
              female={upper_female}
              unspecified={upper_unspecified}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No wingspan data available.
            </p>
          )}
        </div>
        <div>
          <h3 className="text-lg leading-tight">Lower</h3>
          {lower_male || lower_female || lower_unspecified ? (
            <Wingspan
              male={lower_male}
              female={lower_female}
              unspecified={lower_unspecified}
            />
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No wingspan data available.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Wingspan({
  male,
  female,
  unspecified,
}: {
  male: number | null | undefined;
  female: number | null | undefined;
  unspecified: number | null | undefined;
}) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (![male, female, unspecified].some(hasValue)) {
    return null;
  }

  return (
    <ul className="space-y-1 text-gray-700 dark:text-gray-300">
      {hasValue(male) && (
        <li>
          <span className={valueClass}>{male} mm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (♂)"}
          </span>
        </li>
      )}
      {hasValue(female) && (
        <li>
          <span className={valueClass}>{female} mm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (♀)"}
          </span>
        </li>
      )}
      {hasValue(unspecified) && (
        <li>
          <span className={valueClass}>{unspecified} mm</span>
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mr-1">
            {" (Unspecified)"}
          </span>
        </li>
      )}
    </ul>
  );
}

function FlightDuration({ duration }: { duration: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(duration)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Plane className="h-12 w-12" />
      </div>
      <div>
        <p className={valueClass}>
          {duration} month{duration === 1 ? "" : "s"}
        </p>
      </div>
    </div>
  );
}

function CanopyAffinity({ affinity }: { affinity: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(affinity)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="rounded-md bg-gradient-to-br from-teal-500/15 to-emerald-500/15 flex items-center justify-center">
        <Trees className="h-12 w-12" />
      </div>
      <div>
        <p className={valueClass}>{affinity}</p>
      </div>
    </div>
  );
}
