import {
  isAbsentAllYear,
  LepTraits,
  noTraitData,
  parseDiapauseStage,
  parseMonthPresence,
  parseOvipositionStyle,
  parseVoltinism,
  toDiapauseCode,
  toOvipositionCode,
  toVoltinismCode,
} from "@/lib/leptraits";

import { useMemo, type ReactNode } from "react";

import {
  LepTraitDataNote,
  LepTraitDataSourceInfo,
} from "@/components/Attribution";
import {
  AdultPresenceIcon,
  CanopyIcon,
  DiapauseIcon,
  DisturbanceIcon,
  EdgeForestIcon,
  FlightDurationIcon,
  HostPlantAccountsIcon,
  HostPlantFamiliesIcon,
  HostPlantFamilyIcon,
  MoistureIcon,
  OvipositionIcon,
  VoltinismIcon,
  WingspanIcon,
} from "@/components/ui/icons";
import { NoData } from "@/components/NoData";
import { IconContainer } from "@/components/IconContainer";
import {
  commonIconClass,
  DataCard as TraitCard,
  DataSection as TraitSection,
  labelClass,
  rowClass,
  valueClass,
} from "./DataCards";

const hasText = (v: unknown): v is string =>
  typeof v === "string" && v.trim() !== "";
const hasNumber = (v: unknown): v is number =>
  typeof v === "number" && !Number.isNaN(v);

function SpeciesTraits({ traits }: { traits: LepTraits | null }) {
  if (!traits || noTraitData(traits)) {
    return <NoData text="No trait data available." />;
  }
  return (
    <div>
      <TraitSection title="Morphology">
        <TraitCard title="Wingspan" wide>
          <WingspanCard
            upper_male={traits.wingspan_upper_male}
            upper_female={traits.wingspan_upper_female}
            upper_unspecified={traits.wingspan_upper_unspecified}
            lower_male={traits.wingspan_lower_male}
            lower_female={traits.wingspan_lower_female}
            lower_unspecified={traits.wingspan_lower_unspecified}
          />
        </TraitCard>
      </TraitSection>

      <TraitSection title="Life History">
        {hasText(traits.voltinism) && (
          <TraitCard title="Voltinism">
            <Voltinism voltinism={traits.voltinism} />
          </TraitCard>
        )}
        {hasText(traits.diapause_stage) && (
          <TraitCard title="Diapause Stage">
            <DiapauseStage diapause={traits.diapause_stage} />
          </TraitCard>
        )}
        {hasText(traits.oviposition_style) && (
          <TraitCard title="Oviposition Style">
            <OvipositionStyle style={traits.oviposition_style} />
          </TraitCard>
        )}
      </TraitSection>

      <TraitSection title="Habitats">
        {hasText(traits.canopy_affinity) && (
          <TraitCard title="Canopy Affinity">
            <Affinity
              affinity={traits.canopy_affinity}
              icon={<CanopyIcon className={commonIconClass} />}
            />
          </TraitCard>
        )}
        {hasText(traits.edge_affinity) && (
          <TraitCard title="Edge Affinity">
            <Affinity
              affinity={traits.edge_affinity}
              icon={<EdgeForestIcon className={commonIconClass} />}
            />
          </TraitCard>
        )}
        {hasText(traits.moisture_affinity) && (
          <TraitCard title="Moisture Affinity">
            <Affinity
              affinity={traits.moisture_affinity}
              icon={<MoistureIcon className={commonIconClass} />}
            />
          </TraitCard>
        )}
        {hasText(traits.disturbance_affinity) && (
          <TraitCard title="Disturbance Affinity">
            <Affinity
              affinity={traits.disturbance_affinity}
              icon={<DisturbanceIcon className={commonIconClass} />}
            />
          </TraitCard>
        )}
      </TraitSection>

      <TraitSection title="Resources">
        {hasNumber(traits.number_of_hostplant_families) && (
          <TraitCard title="Number of Host Plant Families">
            <NumberOfHostPlants count={traits.number_of_hostplant_families} />
          </TraitCard>
        )}
        {hasText(traits.sole_hostplant_family) && (
          <TraitCard title="Sole Host Plant Family">
            <HostPlantFamilies families={traits.sole_hostplant_family} />
          </TraitCard>
        )}
        {hasText(traits.primary_hostplant_family) && (
          <TraitCard title="Primary Host Plant Family">
            <HostPlantFamilies families={traits.primary_hostplant_family} />
          </TraitCard>
        )}
        {hasText(traits.secondary_hostplant_family) && (
          <TraitCard title="Secondary Host Plant Family">
            <HostPlantFamilies families={traits.secondary_hostplant_family} />
          </TraitCard>
        )}
        {hasText(traits.equal_hostplant_family) && (
          <TraitCard title="Equal Host Plant Family">
            <HostPlantFamilies families={traits.equal_hostplant_family} />
          </TraitCard>
        )}
        {hasNumber(traits.number_of_hostplant_accounts) && (
          <TraitCard title="Number of Host Plant Accounts">
            <HostPlantAccount count={traits.number_of_hostplant_accounts} />
          </TraitCard>
        )}
      </TraitSection>

      <TraitSection title="Phenology">
        {hasNumber(traits.flight_duration) && (
          <TraitCard title="Flight Duration">
            <FlightDuration duration={traits.flight_duration} />
          </TraitCard>
        )}
        <TraitCard title="Adult Presence" wide>
          <div className={rowClass}>
            {/* The strip needs the width more than the icon does, so the
                icon steps aside on a narrow card. */}
            <div className="hidden sm:block">
              <IconContainer>
                <AdultPresenceIcon className={commonIconClass} />
              </IconContainer>
            </div>
            <MonthPresence traits={traits} />
          </div>
        </TraitCard>
      </TraitSection>

      <div className="w-full mt-12 mb-6">
        <LepTraitDataNote />
        <LepTraitDataSourceInfo />
      </div>
    </div>
  );
}

function MonthPresence({ traits }: { traits: LepTraits | null }) {
  // Above every early return. React identifies a hook by call order, so a
  // `useMemo` sitting below the `!traits` guard is only reached on some
  // renders — the moment `traits` arrives after a render without it, the hook
  // order changes and React throws. Latent only because nothing flips it
  // within a mount today.
  const presentAbsentMap = useMemo(
    () => (traits ? parseMonthPresence(traits) : {}),
    [traits]
  );

  if (!traits) {
    return null;
  }

  // Only render if we have data
  if (Object.keys(presentAbsentMap).length === 0) {
    return (
      <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
        No month presence data available.
      </p>
    );
  }

  if (isAbsentAllYear(presentAbsentMap)) {
    return (
      <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
        No data available.
      </p>
    );
  }

  // Twelve equal columns that shrink with the card. The labels are sized
  // against the strip itself (a container query), not the screen: below
  // 24rem the three-letter names no longer fit a column, so each month drops
  // to its initial and the full name stays for screen readers.
  return (
    <div className="@container min-w-0 flex-1">
      <ol
        className="grid grid-cols-12 gap-0.5 @sm:gap-1"
        aria-label="Months when adults are present"
      >
        {Object.entries(presentAbsentMap).map(([month, isPresent]) => (
          <li key={month} className="flex min-w-0 flex-col items-center gap-1">
            <span
              aria-hidden="true"
              className={`h-6 w-full rounded-sm @sm:h-8 ${
                isPresent
                  ? "bg-hunter-green-600 dark:bg-hunter-green-400"
                  : "border border-deep-mocha-300 bg-deep-mocha-200/50 dark:border-deep-mocha-700 dark:bg-deep-mocha-800/50"
              }`}
            />
            <span
              aria-hidden="true"
              className="text-xs leading-none text-deep-mocha-600 dark:text-deep-mocha-300"
            >
              <span className="@sm:hidden">{month.charAt(0)}</span>
              <span className="hidden @sm:inline">{month}</span>
            </span>
            <span className="sr-only">
              {month}: {isPresent ? "present" : "absent"}
            </span>
          </li>
        ))}
      </ol>
      <div
        aria-hidden="true"
        className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-deep-mocha-600 dark:text-deep-mocha-300"
      >
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-hunter-green-600 dark:bg-hunter-green-400" />
          Present
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-sm border border-deep-mocha-300 bg-deep-mocha-200/50 dark:border-deep-mocha-700 dark:bg-deep-mocha-800/50" />
          Absent
        </span>
      </div>
    </div>
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
    <div className={rowClass}>
      <IconContainer>
        <WingspanIcon className="w-20 h-20 m-1" size="lg" />
      </IconContainer>
      <div className="space-y-1">
        <div>
          <h3 className="text-base leading-tight">Upper</h3>
          {upper_male || upper_female || upper_unspecified ? (
            <Wingspan
              male={upper_male}
              female={upper_female}
              unspecified={upper_unspecified}
            />
          ) : (
            <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
              No data available.
            </p>
          )}
        </div>
        <div>
          <h3 className="text-base leading-tight">Lower</h3>
          {lower_male || lower_female || lower_unspecified ? (
            <Wingspan
              male={lower_male}
              female={lower_female}
              unspecified={lower_unspecified}
            />
          ) : (
            <p className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
              No data available.
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
    <ul className="space-y-1 text-deep-mocha-700 dark:text-deep-mocha-300">
      {hasValue(male) && (
        <li>
          <span className={valueClass}>{male.toPrecision(3)} cm</span>
          <span className={labelClass}>{" (♂)"}</span>
        </li>
      )}
      {hasValue(female) && (
        <li>
          <span className={valueClass}>{female.toPrecision(3)} cm</span>
          <span className={labelClass}>{" (♀)"}</span>
        </li>
      )}
      {hasValue(unspecified) && (
        <li>
          <span className={valueClass}>{unspecified.toPrecision(3)} cm</span>
          <span className={labelClass}>{" (Unspecified)"}</span>
        </li>
      )}
    </ul>
  );
}

function FlightDuration({
  duration,
  icon,
}: {
  duration: number | null | undefined;
  /** Supplied when the caller renders at a size other than the card default. */
  icon?: ReactNode;
}) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(duration)) {
    return null;
  }

  return (
    <div className={rowClass}>
      <IconContainer>
        {icon ?? <FlightDurationIcon className={commonIconClass} />}
      </IconContainer>
      <div>
        <p className={valueClass}>
          {duration}{" "}
          <span className={labelClass}>month{duration === 1 ? "" : "s"}</span>
        </p>
      </div>
    </div>
  );
}

function Affinity({
  affinity,
  icon,
}: {
  affinity: string | null | undefined;
  icon?: ReactNode;
}) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(affinity)) {
    return null;
  }

  return (
    <div className={rowClass}>
      <IconContainer>
        {icon ?? <CanopyIcon className={commonIconClass} />}
      </IconContainer>
      <div>
        <p className={valueClass}>{affinity}</p>
      </div>
    </div>
  );
}

function Voltinism({ voltinism }: { voltinism: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(voltinism)) {
    return null;
  }

  const voltinismLabel = parseVoltinism(voltinism);

  return (
    <div className={rowClass}>
      <IconContainer>
        <VoltinismIcon
          className={commonIconClass}
          variant={toVoltinismCode(voltinism)}
        />
      </IconContainer>
      <p className={valueClass}>
        {voltinismLabel.label}{" "}
        {voltinismLabel.description.trim() === "" ? null : (
          <span className={labelClass}>
            {voltinismLabel.description.trim()}
          </span>
        )}
      </p>
    </div>
  );
}

function DiapauseStage({ diapause }: { diapause: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(diapause)) {
    return null;
  }

  const diapauseLabel = parseDiapauseStage(diapause);

  return (
    <div className={rowClass}>
      <IconContainer>
        <DiapauseIcon
          className={commonIconClass}
          variant={toDiapauseCode(diapause)}
        />
      </IconContainer>
      <p className={valueClass}>
        {diapauseLabel.label}{" "}
        {diapauseLabel.description.trim() === "" ? null : (
          <span className={labelClass}>{diapauseLabel.description.trim()}</span>
        )}
      </p>
    </div>
  );
}

function OvipositionStyle({ style }: { style: string | null | undefined }) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(style)) {
    return null;
  }

  const styleLabel = parseOvipositionStyle(style);

  return (
    <div className={rowClass}>
      <IconContainer>
        <OvipositionIcon
          className={commonIconClass}
          variant={toOvipositionCode(style)}
        />
      </IconContainer>
      <p className={valueClass}>{styleLabel}</p>
    </div>
  );
}

function NumberOfHostPlants({ count }: { count: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(count)) {
    return null;
  }

  return (
    <div className={rowClass}>
      <IconContainer>
        <HostPlantFamiliesIcon className={commonIconClass} />
      </IconContainer>
      <div>
        <p className={valueClass}>
          {count}
          <span className={labelClass}>
            {" "}
            {count > 1 ? " families" : " family"}
          </span>
        </p>
      </div>
    </div>
  );
}

function HostPlantFamilies({
  families,
  icon,
}: {
  families: string | null | undefined;
  icon?: ReactNode;
}) {
  const hasValue = (v: unknown): v is string =>
    typeof v === "string" && v.trim() !== "";

  if (!hasValue(families)) {
    return null;
  }

  // Split by commas and trim whitespace
  const familyList = families.split(",").map((f) => f.trim());

  return (
    <div className={rowClass}>
      <IconContainer>
        {icon ?? <HostPlantFamilyIcon className={commonIconClass} />}
      </IconContainer>
      <div>
        <p className={valueClass}>{familyList.join(" · ")}</p>
      </div>
    </div>
  );
}

function HostPlantAccount({ count }: { count: number | null | undefined }) {
  const hasValue = (v: unknown): v is number =>
    typeof v === "number" && !Number.isNaN(v);

  if (!hasValue(count)) {
    return null;
  }

  return (
    <div className={rowClass}>
      <IconContainer>
        <HostPlantAccountsIcon className={commonIconClass} />
      </IconContainer>
      <div>
        <p className={valueClass}>
          {count}{" "}
          <span className={labelClass}>
            host plant account{count === 1 ? "" : "s"}
          </span>
        </p>
      </div>
    </div>
  );
}

export { SpeciesTraits, WingspanCard, FlightDuration, Affinity, Voltinism };
