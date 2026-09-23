"use client";

import { useEffect, useState } from "react";

import { ColAttribution } from "@/components/Attribution";
import { TextLoading } from "@/components/Loadings";
import PaginationControls from "@/components/PaginationControls";
import Tips from "@/components/Tips";
import { toneClasses } from "@/lib/codeTone";
import { TaxonomyData } from "@/lib/speciesData";
import {
  ColReference,
  NameUsage,
  PRIMARY_TYPE_STATUSES,
  TaxonomyDetail,
  TypeSpecimen,
  fetchTaxonomyDetail,
} from "@/lib/taxonomyDetail";
import { ClassificationLadder } from "./ClassificationLadder";

// Some taxa carry dozens of paratypes; the name-bearing type is what a reader
// comes for, and it always sorts first.
const INITIAL_TYPES = 5;

// A widespread species can carry a hundred or more synonyms and subspecies
// names; one page of them is enough to read.
const USAGES_PER_PAGE = 20;

interface TaxonomyPageProps {
  taxonomy: TaxonomyData | null;
  /** The route slug, which the backend resolves to the accepted taxon. */
  speciesName: string;
}

type DetailState =
  | { speciesName: string; status: "loaded"; detail: TaxonomyDetail | null }
  | { speciesName: string; status: "failed" };

export default function TaxonomyPage({
  taxonomy,
  speciesName,
}: TaxonomyPageProps) {
  // Keyed by the species it was fetched for, so a change of species reads as
  // loading without resetting state synchronously inside the effect.
  const [state, setState] = useState<DetailState | null>(null);

  useEffect(() => {
    if (!speciesName.trim()) return;
    let isMounted = true;
    fetchTaxonomyDetail(speciesName)
      .then((detail) => {
        if (isMounted) setState({ speciesName, status: "loaded", detail });
      })
      .catch((error) => {
        console.error("Error fetching taxonomy detail:", error);
        if (isMounted) setState({ speciesName, status: "failed" });
      });
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  const loading = state?.speciesName !== speciesName;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2 space-y-5 min-w-0">
        {loading ? (
          <TextLoading msg="Loading taxonomy" />
        ) : state.status === "failed" ? (
          <Empty text="Taxonomy details could not be loaded right now. Please try again later." />
        ) : !state.detail ? (
          <Empty text="Catalogue of Life has no species record for this name, so there is no nomenclature or type material to show." />
        ) : (
          <DetailSections detail={state.detail} />
        )}
      </div>

      <div className="lg:col-span-1 space-y-5 min-w-0">
        <Card title="Classification">
          <ClassificationLadder taxonomy={taxonomy} />
          {taxonomy ? <ClassificationFacts taxonomy={taxonomy} /> : null}
          <ColAttribution />
        </Card>
      </div>
    </div>
  );
}

/** What the ladder leaves out: status, common name and the CoL record. */
function ClassificationFacts({ taxonomy }: { taxonomy: TaxonomyData }) {
  return (
    <div className="mt-3 pt-3 border-t border-deep-mocha-200 dark:border-deep-mocha-700">
      <table className="w-full min-w-0">
        <tbody>
          <Row label="Status">
            <span className="capitalize">
              {taxonomy.taxonomicStatus || "Unknown"}
            </span>
          </Row>
          {taxonomy.vernacularName ? (
            <Row label="Common Name">{taxonomy.vernacularName}</Row>
          ) : null}
          {taxonomy.colLink ? (
            <Row label="Catalogue of Life">
              <a
                href={taxonomy.colLink}
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
    </div>
  );
}

function DetailSections({ detail }: { detail: TaxonomyDetail }) {
  const unavailable = !detail.detailAvailable;
  return (
    <>
      <Card title="Nomenclature">
        <NomenclatureTable detail={detail} />
      </Card>

      <Card
        title="Type Material"
        count={detail.typeMaterial.length || undefined}
      >
        {unavailable ? (
          <Muted>Type material has not been loaded on this server.</Muted>
        ) : detail.typeMaterial.length === 0 ? (
          <Muted>No type material recorded in Catalogue of Life.</Muted>
        ) : (
          <TypeMaterialList types={detail.typeMaterial} />
        )}
      </Card>

      {/* A plain heading rather than a card, as on the database search page:
          the table carries its own frame. */}
      <section aria-labelledby="name-usage-heading" className="pt-3">
        <div className="mb-4">
          <h2
            id="name-usage-heading"
            className="text-2xl font-bold tracking-tight text-deep-mocha-800 dark:text-deep-mocha-100 font-serif"
          >
            Name Usage ({detail.nameUsages.length})
          </h2>
          <Tips message="The accepted name comes first, then the original combination it was described under, then every other synonym by year of publication." />
        </div>
        <NameUsageTable
          // Remount on a new species so its table starts on page one.
          key={detail.nomenclature.acceptedName}
          usages={detail.nameUsages}
        />
        <ColAttribution />
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

function Card({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl flex items-baseline gap-2">
        <h2 className="text-2xl font-semibold">{title}</h2>
        {count ? (
          <span className="text-sm text-deep-mocha-500 dark:text-deep-mocha-400">
            {count}
          </span>
        ) : null}
      </div>
      <div className="p-4 text-sm text-deep-mocha-700 dark:text-deep-mocha-300">
        {children}
      </div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-xl bg-white/40 dark:bg-deep-mocha-800/40 p-6">
      <Muted>{text}</Muted>
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-deep-mocha-500 dark:text-deep-mocha-400">{children}</p>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  // The label, the colon and the value each get a column, so every value
  // starts at the same x.
  return (
    <tr>
      <td className="font-medium align-top whitespace-nowrap py-0.5">
        {label}
      </td>
      <td className="font-medium align-top px-1 py-0.5">:</td>
      {/* w-full lets the value take the slack, so the label column stays
          as narrow as its longest label. */}
      <td className="w-full wrap-break-words whitespace-normal align-top py-0.5">
        {children}
      </td>
    </tr>
  );
}

function Badge({
  tone,
  children,
}: {
  tone: Parameters<typeof toneClasses>[0];
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize whitespace-nowrap ${toneClasses(tone)}`}
    >
      {children}
    </span>
  );
}

function ScientificName({
  name,
  authorship,
}: {
  name: string;
  authorship?: string | null;
}) {
  return (
    <>
      <i className="italic">{name}</i>
      {authorship ? <span> {authorship}</span> : null}
    </>
  );
}

function Reference({
  reference,
  page,
}: {
  reference: ColReference;
  page?: string | null;
}) {
  return (
    <span>
      {/* The page follows the citation, so its closing period moves after
          the page rather than landing in front of the comma. */}
      {page
        ? `${reference.citation.replace(/\.$/, "")}, p. ${page}.`
        : reference.citation}
      {reference.link ? (
        <>
          {" "}
          <a
            href={reference.link}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            {reference.doi ? "DOI" : "Link"}
          </a>
        </>
      ) : null}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Nomenclature
// ---------------------------------------------------------------------------

function NomenclatureTable({ detail }: { detail: TaxonomyDetail }) {
  const nomenclature = detail.nomenclature;
  return (
    <table className="w-full min-w-0">
      <tbody>
        <Row label="Accepted Name">
          <ScientificName
            name={nomenclature.acceptedName}
            authorship={nomenclature.authorship}
          />
        </Row>
        <Row label="Original Combination">
          {nomenclature.originalCombination ? (
            <ScientificName
              name={nomenclature.originalCombination}
              authorship={nomenclature.originalAuthorship}
            />
          ) : nomenclature.isOriginalCombination ? (
            <span>Same as the accepted name</span>
          ) : (
            // Parenthesized authorship: described in another genus, but CoL
            // does not link which combination.
            <span className="text-deep-mocha-500 dark:text-deep-mocha-400">
              Described in another genus; not recorded
            </span>
          )}
        </Row>
        {nomenclature.year ? (
          <Row label="Year Described">{nomenclature.year}</Row>
        ) : null}
        <Row label="Original Publication">
          {nomenclature.originalPublication ? (
            <Reference
              reference={nomenclature.originalPublication}
              page={nomenclature.originalPublicationPage}
            />
          ) : (
            <span className="text-deep-mocha-500 dark:text-deep-mocha-400">
              Not recorded
            </span>
          )}
        </Row>
        {nomenclature.nameStatus ? (
          <Row label="Nomenclatural Status">
            <span className="capitalize">{nomenclature.nameStatus}</span>
          </Row>
        ) : null}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Type material
// ---------------------------------------------------------------------------

const regionNames = (() => {
  try {
    return new Intl.DisplayNames(["en"], { type: "region" });
  } catch {
    return null;
  }
})();

/** CoL records the country as an ISO code; show its name when it is one. */
function countryName(code: string | null): string | null {
  if (!code) return null;
  if (!/^[A-Za-z]{2}$/.test(code)) return code;
  try {
    return regionNames?.of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

function sexLabel(sex: string | null): string | null {
  if (!sex) return null;
  const value = sex.toLowerCase();
  if (value === "male") return "♂ Male";
  if (value === "female") return "♀ Female";
  return sex;
}

function TypeMaterialList({ types }: { types: TypeSpecimen[] }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? types : types.slice(0, INITIAL_TYPES);

  return (
    <div className="space-y-3">
      {shown.map((specimen, index) => (
        <TypeSpecimenCard key={index} specimen={specimen} />
      ))}
      {types.length > INITIAL_TYPES ? (
        <button
          type="button"
          onClick={() => setShowAll((prev) => !prev)}
          className="text-sm underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
        >
          {showAll ? "Show fewer" : `Show all ${types.length}`}
        </button>
      ) : null}
    </div>
  );
}

function TypeSpecimenCard({ specimen }: { specimen: TypeSpecimen }) {
  const primary = PRIMARY_TYPE_STATUSES.has(specimen.status);
  const repository = [specimen.institutionCode, specimen.catalogNumber]
    .filter(Boolean)
    .join(" ");
  const country = countryName(specimen.country);
  // CoL localities often already start with the country.
  const place =
    specimen.locality && country && specimen.locality.includes(country)
      ? specimen.locality
      : [specimen.locality, country].filter(Boolean).join(" · ");
  const coordinates =
    specimen.latitude !== null && specimen.longitude !== null
      ? `${specimen.latitude.toFixed(2)}, ${specimen.longitude.toFixed(2)}`
      : null;
  const collected = [specimen.collector, specimen.date]
    .filter(Boolean)
    .join(", ");

  return (
    <div
      className={`rounded-lg border p-3 ${
        primary
          ? "border-hunter-green-400/60 dark:border-hunter-green-700"
          : "border-deep-mocha-200 dark:border-deep-mocha-700"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <Badge tone={primary ? "matched" : "neutral"}>{specimen.status}</Badge>
        {repository ? <span className="font-medium">{repository}</span> : null}
        {specimen.typifiedName ? (
          <span className="text-deep-mocha-500 dark:text-deep-mocha-400">
            of <i className="italic">{specimen.typifiedName}</i>
          </span>
        ) : null}
      </div>
      <table className="w-full min-w-0">
        <tbody>
          {sexLabel(specimen.sex) ? (
            <Row label="Sex">{sexLabel(specimen.sex)}</Row>
          ) : null}
          {place ? <Row label="Locality">{place}</Row> : null}
          {coordinates ? <Row label="Coordinates">{coordinates}</Row> : null}
          {specimen.altitude ? (
            <Row label="Altitude">{specimen.altitude}</Row>
          ) : null}
          {collected ? <Row label="Collected">{collected}</Row> : null}
          {specimen.host ? <Row label="Host">{specimen.host}</Row> : null}
          {specimen.citation ? (
            <Row label="Citation">{specimen.citation}</Row>
          ) : null}
          {specimen.reference ? (
            <Row label="Source">
              <Reference
                reference={specimen.reference}
                page={specimen.referencePage}
              />
            </Row>
          ) : null}
          {specimen.link ? (
            <Row label="Record">
              <a
                href={specimen.link}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
              >
                View specimen
              </a>
            </Row>
          ) : null}
          {specimen.remarks ? (
            <Row label="Remarks">{specimen.remarks}</Row>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Name usage
// ---------------------------------------------------------------------------

function usageBadge(usage: NameUsage) {
  if (usage.isAccepted) return <Badge tone="matched">{usage.status}</Badge>;
  if (usage.isRecorded) return <Badge tone="unmatched">Recorded here</Badge>;
  return <Badge tone="neutral">{usage.status}</Badge>;
}

function NameUsageTable({ usages }: { usages: NameUsage[] }) {
  const [page, setPage] = useState(1);
  if (usages.length === 0) {
    return <Muted>No name usages recorded.</Muted>;
  }
  // Header, row and container styles match the specimen table on the
  // database search page, so the two tables read as one system.
  const headerClass = "px-4 py-3 font-semibold whitespace-nowrap";
  const cellClass = "px-4 py-3 align-top";

  const pageCount = Math.ceil(usages.length / USAGES_PER_PAGE);
  const start = (page - 1) * USAGES_PER_PAGE;
  const shown = usages.slice(start, start + USAGES_PER_PAGE);

  return (
    <>
      {/* Scrolls inside its own box on a phone rather than widening the page. */}
      <div className="overflow-x-auto w-full rounded-2xl border border-deep-mocha-200 dark:border-deep-mocha-700/80 shadow-xs bg-white/40 dark:bg-deep-mocha-800/40 backdrop-blur-md">
        <table className="w-full min-w-[36rem] text-left text-sm text-deep-mocha-700 dark:text-deep-mocha-300 border-collapse">
          <thead className="bg-hunter-green-500/10 dark:bg-hunter-green-500/20 text-hunter-green-800 dark:text-hunter-green-300 font-semibold tracking-wider text-xs uppercase border-b border-deep-mocha-200 dark:border-deep-mocha-700">
            <tr>
              <th className={headerClass}>Name</th>
              <th className={headerClass}>Status</th>
              <th className={headerClass}>Published in</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-deep-mocha-200/50 dark:divide-deep-mocha-700/50">
            {shown.map((usage, index) => (
              <tr
                key={usage.colId ?? `${usage.name}-${start + index}`}
                className="hover:bg-hunter-green-50/50 dark:hover:bg-hunter-green-950/20 transition-colors"
              >
                <td className={`${cellClass} font-medium`}>
                  <ScientificName
                    name={usage.name}
                    authorship={usage.authorship}
                  />
                  {usage.isBasionym ? (
                    <div className="text-xs font-normal text-hunter-green-700 dark:text-hunter-green-300">
                      Original combination
                    </div>
                  ) : null}
                  {usage.rank && usage.rank !== "species" ? (
                    <div className="text-xs font-normal text-deep-mocha-500 dark:text-deep-mocha-400 capitalize">
                      {usage.rank}
                    </div>
                  ) : null}
                </td>
                <td className={cellClass}>{usageBadge(usage)}</td>
                <td className={cellClass}>
                  {usage.publishedIn ? (
                    <Reference
                      reference={usage.publishedIn}
                      page={usage.publishedInPage}
                    />
                  ) : usage.year ? (
                    <span>{usage.year}</span>
                  ) : (
                    <span className="text-deep-mocha-400 dark:text-deep-mocha-600">
                      —
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationControls
        currentPage={page}
        totalPages={pageCount}
        totalItems={usages.length}
        itemsPerPage={USAGES_PER_PAGE}
        label="names"
        onPageChange={setPage}
      />
    </>
  );
}
