/**
 * The code vocabularies, written out for the resources page.
 *
 * Everywhere else in the UI a code explains itself through a hover hint fed
 * by `GET /taxonomy/codes` and `GET /geography/codes`. That is the right
 * shape for a badge on one specimen and the wrong shape for a reference
 * page, which has to list every code whether or not a record on screen uses
 * it — and has to render on the server, before any request is made.
 *
 * The prose is copied from `backend/app/services/col_match_codes.py` and
 * `backend/app/services/geo_validation_codes.py`, which themselves mirror
 * the enums in `packages/colharmonize` and `packages/geoharmonize`. If a
 * description changes there, change it here too.
 */

export interface CodeRow {
  code: string;
  description: string;
}

/** colharmonize `UpdateStatus`. */
export const UPDATE_STATUS_ROWS: CodeRow[] = [
  {
    code: "MATCHED",
    description: "One accepted taxon was resolved with sufficient evidence.",
  },
  {
    code: "AMBIGUOUS",
    description:
      "Candidates were found, but the evidence did not identify one accepted taxon.",
  },
  {
    code: "UNMATCHED",
    description:
      "No eligible accepted taxon was found, or the input was invalid or unsupported.",
  },
];

/** colharmonize `MatchMethod`, strongest first. The two terminal values,
 *  AMBIGUOUS and UNMATCHED, are outcomes rather than methods and are
 *  covered by the outcome table above. */
export const MATCH_METHOD_ROWS: CodeRow[] = [
  {
    code: "EXACT_ACCEPTED",
    description:
      "The normalized input name exactly matched an accepted name usage.",
  },
  {
    code: "EXACT_SYNONYM",
    description:
      "The normalized input name exactly matched a synonym of the accepted taxon.",
  },
  {
    code: "EXACT_CANONICAL",
    description:
      "The parsed genus and epithet exactly matched an accepted canonical binomial.",
  },
  {
    code: "UNIQUE_FAMILY_EPITHET",
    description:
      "One accepted taxon matched the input family and specific epithet.",
  },
  {
    code: "SPELLING_GENUS",
    description:
      "The family and epithet matched while genus spelling similarity resolved the taxon.",
  },
  {
    code: "SPELLING_EPITHET",
    description:
      "The family and genus matched while epithet edit distance resolved the taxon.",
  },
  {
    code: "FUZZY_TYPO",
    description:
      "Family-restricted spelling similarity resolved both genus and epithet.",
  },
];

/** colharmonize reason codes, set on inputs it declined to match at all. */
export const REASON_CODE_ROWS: CodeRow[] = [
  {
    code: "UNSUPPORTED_RANK",
    description:
      "The recorded rank is not one of species, subspecies, or genus, so the name was not matched.",
  },
  {
    code: "INVALID_BINOMIAL",
    description:
      "The recorded name could not be parsed as a usable binomial, so the name was not matched.",
  },
];

/** geoharmonize `CoordinateValidationStatus`, in precedence order. */
export const VALIDATION_STATUS_ROWS: CodeRow[] = [
  { code: "MISSING_COORDINATE", description: "No coordinate was recorded." },
  {
    code: "COORDINATE_OUT_OF_RANGE",
    description:
      "The coordinate is outside the range of valid latitudes or longitudes.",
  },
  { code: "ZERO_COORDINATE", description: "The coordinate is 0, 0." },
  {
    code: "NO_REFERENCE_MATCH",
    description: "The coordinate falls outside every known boundary.",
  },
  {
    code: "AMBIGUOUS_REFERENCE",
    description: "The coordinate falls where several regions meet.",
  },
  {
    code: "COUNTRY_MISMATCH",
    description:
      "The coordinate falls in a different country than the one recorded.",
  },
  {
    code: "ADM1_MISMATCH",
    description:
      "The coordinate falls in a different state or province than the one recorded.",
  },
  { code: "VALID", description: "The coordinate matches the recorded locality." },
];

/** geoharmonize `CoordinateCheck`. */
export const COORDINATE_CHECK_ROWS: CodeRow[] = [
  {
    code: "MISSING_COORDINATE",
    description:
      "Latitude or longitude was missing, non-finite, or could not be parsed.",
  },
  {
    code: "LATITUDE_OUT_OF_RANGE",
    description: "Latitude was outside -90 to 90 degrees.",
  },
  {
    code: "LONGITUDE_OUT_OF_RANGE",
    description: "Longitude was outside -180 to 180 degrees.",
  },
  {
    code: "ZERO_COORDINATE",
    description: "Both latitude and longitude were zero.",
  },
  {
    code: "VALID_COORDINATE",
    description: "Both coordinates were finite and in range.",
  },
];

/** geoharmonize `CountryCheck`. */
export const COUNTRY_CHECK_ROWS: CodeRow[] = [
  {
    code: "COUNTRY_MATCH",
    description: "Recorded and coordinate-derived countries agree.",
  },
  {
    code: "COUNTRY_MISMATCH",
    description: "Recorded and coordinate-derived countries differ.",
  },
  {
    code: "COUNTRY_NOT_PROVIDED",
    description: "No recorded country was supplied.",
  },
  {
    code: "NO_REFERENCE_MATCH",
    description: "The coordinate intersected no reference region.",
  },
  {
    code: "AMBIGUOUS_REFERENCE",
    description:
      "The coordinate intersected multiple distinct reference regions.",
  },
  {
    code: "NOT_EVALUATED",
    description: "Country was not checked because coordinates were invalid.",
  },
];

/** geoharmonize `Adm1Check`. */
export const ADM1_CHECK_ROWS: CodeRow[] = [
  {
    code: "ADM1_MATCH",
    description: "Recorded and coordinate-derived ADM1 values agree.",
  },
  {
    code: "ADM1_MISMATCH",
    description: "Recorded and coordinate-derived ADM1 values differ.",
  },
  {
    code: "ADM1_NOT_PROVIDED",
    description: "No recorded ADM1 value was supplied.",
  },
  {
    code: "NO_ADM1_REFERENCE_MATCH",
    description: "The reference region had no ADM1 name.",
  },
  {
    code: "NO_REFERENCE_MATCH",
    description: "The coordinate intersected no reference region.",
  },
  {
    code: "AMBIGUOUS_REFERENCE",
    description:
      "The coordinate intersected multiple distinct reference regions.",
  },
  {
    code: "NOT_EVALUATED",
    description: "ADM1 was not checked because coordinates were invalid.",
  },
];
