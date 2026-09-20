import { ColAttribution } from "@/components/Attribution";
import {
  COL_RANK_ORDER,
  CORE_COL_RANKS,
  ITALIC_COL_RANKS,
  rankValue,
} from "@/lib/colTaxonomy";
import { TaxonomyData } from "@/lib/speciesData";

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <tr>
      <td className="font-medium pr-1 align-top whitespace-nowrap">{label}:</td>
      <td className="wrap-break-words whitespace-normal pl-2">{children}</td>
    </tr>
  );
}

export function SpeciesClassification({
  taxonomyData,
}: {
  taxonomyData: TaxonomyData | null;
}) {
  if (!taxonomyData) {
    return (
      <p className="text-deep-mocha-500 dark:text-deep-mocha-400">
        No classification data available.
      </p>
    );
  }

  // The core ranks always appear, so their absence is visible. The
  // intermediate ranks Catalogue of Life adds — subphylum, superfamily, tribe
  // and the rest — are populated unevenly, and a row reading "Unknown" for
  // each of them would say nothing; they appear only when there is a value.
  const rows = COL_RANK_ORDER.map((rank) => ({
    rank,
    value: rankValue(taxonomyData, rank),
  })).filter(({ rank, value }) => CORE_COL_RANKS.has(rank) || value);

  const acceptedName = taxonomyData.acceptedName;
  const recordedName = taxonomyData.inputName;
  const nameWasUpdated = !!recordedName && recordedName !== acceptedName;

  return (
    <div className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">Classification</h2>
      </div>
      <div className="p-4 ml-4">
        <table className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300 w-full min-w-0">
          <tbody>
            {rows.map(({ rank, value }) => (
              <Row key={rank} label={rank.charAt(0).toUpperCase() + rank.slice(1)}>
                {ITALIC_COL_RANKS.has(rank) ? (
                  <i className="italic">{value ?? "Unknown"}</i>
                ) : (
                  (value ?? "Unknown")
                )}
              </Row>
            ))}

            {taxonomyData.authorship ? (
              <Row label="Authorship">{taxonomyData.authorship}</Row>
            ) : null}

            <Row label="Taxonomic Status">
              <span className="capitalize">
                {taxonomyData.taxonomicStatus || "Unknown"}
              </span>
            </Row>

            {nameWasUpdated ? (
              <>
                <Row label="Accepted Name">
                  <i className="italic">{acceptedName}</i>
                  {taxonomyData.acceptedRank === "genus" ? (
                    <span className="text-deep-mocha-500"> (genus only)</span>
                  ) : null}
                </Row>
                <Row label="Recorded As">
                  {/* Kept visible so a reader who searched the old name can
                      see why the page is showing a different one. */}
                  <i className="italic text-deep-mocha-500">{recordedName}</i>
                </Row>
              </>
            ) : null}

            {taxonomyData.vernacularName ? (
              <Row label="Common Name">{taxonomyData.vernacularName}</Row>
            ) : null}

            {taxonomyData.colLink ? (
              <Row label="Catalogue of Life">
                <a
                  href={taxonomyData.colLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-blue-700"
                >
                  View record
                </a>
              </Row>
            ) : null}
          </tbody>
        </table>

        <ColAttribution />
      </div>
    </div>
  );
}
