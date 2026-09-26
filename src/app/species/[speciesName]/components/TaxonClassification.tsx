import Link from "next/link";

import { ColAttribution } from "@/components/Attribution";
import {
  COL_RANK_ORDER,
  CORE_COL_RANKS,
  ITALIC_COL_RANKS,
  rankValue,
} from "@/lib/colTaxonomy";
import { familyHref, genusHref, orderHref } from "@/lib/taxonSlug";
import { TaxonomyData } from "@/lib/speciesData";

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  // The colon sits in a column of its own so every value starts at the same
  // x: with it glued to the label, each row's colon landed wherever that
  // label happened to end.
  return (
    <tr>
      <td className="font-medium align-top whitespace-nowrap">{label}</td>
      <td className="font-medium align-top px-1">:</td>
      <td className="wrap-break-words whitespace-normal align-top">
        {children}
      </td>
    </tr>
  );
}

/**
 * One rank's value, linked when that rank has a page.
 *
 * Only order (Lepidoptera alone), family and genus do. Reading a classification is where someone is
 * most likely to want to go up a level, and until these rows were links the
 * only way there was the breadcrumb.
 */
function RankValue({ rank, value }: { rank: string; value: string | null }) {
  const label = value ?? "Unknown";
  const body = ITALIC_COL_RANKS.has(rank) ? (
    <i className="italic">{label}</i>
  ) : (
    label
  );

  if (!value) return body;
  const href =
    rank === "order"
      ? orderHref(value)
      : rank === "family"
        ? familyHref(value)
        : rank === "genus"
          ? genusHref(value)
          : null;
  if (!href) return body;

  return (
    <Link
      href={href}
      className="hover:underline text-pacific-blue-700 dark:text-pacific-blue-300"
    >
      {body}
    </Link>
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
  // The name this page was looked up under. Only used to decide whether the
  // accepted name is worth stating; it is not shown, because a page-level
  // "recorded as" would speak for images that were recorded differently.
  const queriedName = taxonomyData.inputName;
  const nameWasUpdated = !!queriedName && queriedName !== acceptedName;

  return (
    <div className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">Classification</h2>
      </div>
      <div className="p-4 ml-4">
        <table className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300 w-full min-w-0">
          <tbody>
            {rows.map(({ rank, value }) => (
              <Row
                key={rank}
                label={rank.charAt(0).toUpperCase() + rank.slice(1)}
              >
                <RankValue rank={rank} value={value} />
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
              // No "Recorded As" here. What a record called this taxon is a
              // property of that occurrence, not of the taxon: the images on
              // this page can carry several different recorded names, and one
              // of them presented as the page's own would be wrong. The Image
              // Metadata panel shows it per image instead.
              <Row label="Accepted Name">
                <i className="italic">{acceptedName}</i>
                {taxonomyData.acceptedRank === "genus" ? (
                  <span className="text-deep-mocha-500"> (genus only)</span>
                ) : null}
              </Row>
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
                  className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
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
