export interface LepTraits {
  wingspan_lower_female?: number;
  wingspan_upper_female?: number;
  wingspan_lower_male?: number;
  wingspan_upper_male?: number;
  wingspan_lower_unspecified?: number;
  wingspan_upper_unspecified?: number;
  forewing_lower_female?: number;
  forewing_upper_female?: number;
  forewing_lower_male?: number;
  forewing_upper_male?: number;
  forewing_lower_unspecified?: number;
  forewing_upper_unspecified?: number;
  jan_adult_presence?: string;
  feb_adult_presence?: string;
  mar_adult_presence?: string;
  apr_adult_presence?: string;
  may_adult_presence?: string;
  jun_adult_presence?: string;
  jul_adult_presence?: string;
  aug_adult_presence?: string;
  sep_adult_presence?: string;
  oct_adult_presence?: string;
  nov_adult_presence?: string;
  dec_adult_presence?: string;
  flight_duration?: number;
  diapause_stage?: string;
  voltinism?: string;
  oviposition_style?: string;
  canopy_affinity?: string;
  edge_affinity?: string;
  moisture_affinity?: string;
  disturbance_affinity?: string;
  number_of_hostplant_families?: number;
  sole_hostplant_family?: string;
  primary_hostplant_family?: string;
  secondary_hostplant_family?: string;
  equal_hostplant_family?: string;
  number_of_hostplant_accounts?: number;
  date_created?: string;
}

export interface Voltinism {
  label: string;
  description: string;
}

const voltinismLabels: Record<string, Voltinism> = {
  u: {
    label: "Univoltine",
    description: "(1 generation/year)",
  },
  b: {
    label: "Bivoltine",
    description: "(2 generations/year)",
  },
  m: {
    label: "Multivoltine",
    description: "(>2 generations/year)",
  },
  na: { label: "Unknown", description: "" },
};

export interface DiapauseStage {
  label: string;
  description: string;
}

const diapauseStageLabels: Record<string, DiapauseStage> = {
  l: { label: "Larva", description: "Larva overwinters" },
  p: { label: "Pupa", description: "Pupa overwinters" },
  pl: {
    label: "Pupa or Larva",
    description: "Either pupa or larva overwinters (polymorphic or uncertain)",
  },
  a: { label: "Adult", description: "Adult overwinters" },
  na: { label: "No diapause or data unavailable", description: "" },
};

const ovipositionStyle: Record<string, string> = {
  s: "Solitary",
  g: "Gregarious",
  sc: "Scattered",
  na: "Unknown",
};

const monthKeys = [
  "jan_adult_presence",
  "feb_adult_presence",
  "mar_adult_presence",
  "apr_adult_presence",
  "may_adult_presence",
  "jun_adult_presence",
  "jul_adult_presence",
  "aug_adult_presence",
  "sep_adult_presence",
  "oct_adult_presence",
  "nov_adult_presence",
  "dec_adult_presence",
] as const;
type MonthKey = (typeof monthKeys)[number];
export const monthAbbr = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/* 
Parses month presence traits into a structured object.
Returns an object with month abbreviations as keys and boolean values indicating presence.
API output example:
jan adult presence: Absent
feb adult presence: Absent
mar adult presence: Absent
apr adult presence: Present
may adult presence: Present
jun adult presence: Present
jul adult presence: Present
aug adult presence: Present
sep adult presence: Present
oct adult presence: Present
nov adult presence: Absent
dec adult presence: Absent
    Resulting object:
{
  jan: false,
  feb: false,
  mar: false,
  apr: true,
  may: true,
  jun: true,
  jul: true,
  aug: true,
  sep: true,
  oct: true,
  nov: false,
  dec: false
}  
*/
function parseMonthPresence(traits: LepTraits): Record<string, boolean> {
  const monthMap: Record<string, boolean> = {}; // Move inside function

  monthKeys.forEach((key: MonthKey, index) => {
    if (key in traits) {
      const presence = traits[key];
      monthMap[monthAbbr[index]] = presence?.toLowerCase() === "present";
    }
  });

  return monthMap;
}

function parseVoltinism(voltinism: string | undefined): Voltinism {
  const defaultVoltinism = { label: "Unknown", description: "" };
  if (!voltinism || voltinism.trim() === "") {
    return defaultVoltinism;
  }
  const value = voltinism.toLowerCase();
  return voltinismLabels[value] || defaultVoltinism;
}

function parseDiapauseStage(diapause: string | undefined): DiapauseStage {
  const defaultStage = {
    label: "No diapause or data unavailable",
    description: "",
  };
  if (!diapause || diapause.trim() === "") {
    return defaultStage;
  }
  const value = diapause.toLowerCase();
  return diapauseStageLabels[value] || defaultStage;
}

function parseOvipositionStyle(style: string | undefined): string {
  if (!style || style.trim() === "") {
    return "Unknown";
  }
  const value = style.toLowerCase();
  return ovipositionStyle[value] || "Unknown";
}

function isAbsentAllYear(presenceMap: Record<string, boolean>): boolean {
  return Object.values(presenceMap).every((present) => present === false);
}

export {
  parseMonthPresence,
  parseVoltinism,
  isAbsentAllYear,
  parseDiapauseStage,
  parseOvipositionStyle,
};
