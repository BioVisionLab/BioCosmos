import { ImageLoading } from "@/components/Loadings";
import SearchForm from "@/components/SearchForm";
import PaginationControls from "@/components/PaginationControls";
import Tips from "@/components/Tips";
import { CoordinateStatusBadge, TaxonStatusBadge } from "@/components/CodeHint";
import { ColAttribution, GadmAttribution } from "@/components/Attribution";
import type { CoordinateValidationStatusCode } from "@/lib/geoValidation";
import {
  DbResultItems,
  SpecimenMetadata,
  searchDatabase,
} from "@/lib/dbSearch";
import { fetchSpeciesThumbnail, imageUrlById } from "@/lib/images";
import { safeWebUrl } from "@/lib/imageMetadata";
import {
  cleanSpeciesName,
  formatSpeciesNameForUrl,
  toBinomialName,
} from "@/lib/names";
import { speciesPageHref } from "@/lib/taxonSlug";
import { FlaskConical } from "lucide-react";
import SearchFieldSelect, {
  type SearchFieldGroup,
} from "@/components/SearchFieldSelect";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { SpecimenImageModal } from "@/components/SpecimenImageModal";
import BackLink from "@/components/BackLink";

const FIELD_GROUPS: SearchFieldGroup[] = [
  { options: [{ value: "all", label: "All Fields" }] },
  {
    label: "Taxonomy (Highest to Lowest Rank)",
    options: [
      { value: "kingdom", label: "Kingdom" },
      { value: "phylum", label: "Phylum" },
      { value: "class", label: "Class" },
      { value: "order", label: "Order" },
      { value: "family", label: "Family" },
      { value: "species", label: "Species" },
    ],
  },
  {
    label: "Specimen Metadata",
    options: [
      { value: "common_name", label: "Common Name" },
      { value: "class_dv", label: "Dorso/Ventral View" },
      { value: "sex", label: "Sex" },
      { value: "life_stage", label: "Life Stage" },
      { value: "source_db", label: "Source Database" },
      { value: "update_status", label: "Taxon Status" },
    ],
  },
  {
    label: "Geography",
    options: [
      { value: "country", label: "Country" },
      { value: "state_province", label: "State / Province" },
      { value: "county", label: "County" },
      { value: "locality", label: "Locality" },
      { value: "coordinate", label: "Coordinate (10,000 km² area)" },
      { value: "validation_status", label: "Coordinate Status" },
    ],
  },
];

const IMAGE_SIZE = 128;
const SPECIMEN_THUMB_SIZE = 48;

function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function HighlightText({
  text,
  highlight,
  isMatched,
}: {
  text: string | null | undefined;
  highlight: string;
  isMatched: boolean;
}) {
  if (!text)
    return (
      <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
    );
  if (!isMatched || !highlight) return <>{text}</>;

  // Substring matching case-insensitive
  const regex = new RegExp(`(${escapeRegExp(highlight)})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) =>
        regex.test(part) ? (
          <mark
            key={index}
            className="bg-yellow-200 dark:bg-yellow-800/80 text-black dark:text-white px-0.5 rounded-xs"
          >
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

/**
 * Wrap children in a link to the species page, when there is one to link to.
 *
 * The backend names the page (`species_key`) and leaves it null for a result
 * with none, such as one identified only to genus. The result is still worth
 * showing, so the card renders without pretending to lead somewhere.
 */
function MaybeSpeciesLink({
  speciesKey,
  className,
  children,
}: {
  speciesKey: string | null;
  className?: string;
  children: React.ReactNode;
}) {
  const href = speciesPageHref(speciesKey);
  if (!href) {
    return <div className={className}>{children}</div>;
  }
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

/**
 * The Species cell: the Catalogue of Life accepted name, with the name as
 * recorded beneath it when the two differ.
 *
 * The link targets the page the backend chose (`species_key`): the accepted
 * species' canonical recorded spelling. Neither the accepted slug nor this
 * record's own spelling will do — the first can open an empty gallery, the
 * second a page orphaned under a synonym or misspelling.
 */
function renderTaxonCell(specimen: SpecimenMetadata, query: string) {
  const matched = specimen.matched_fields || [];
  const isMatched = matched.includes("species");
  const accepted = specimen.display_accepted_name
    ? toBinomialName(specimen.display_accepted_name)
    : specimen.display_accepted_name;
  const recorded = specimen.species;

  const recordedLabel = recorded
    ? toBinomialName(cleanSpeciesName(recorded))
    : "";
  const differs =
    !!accepted &&
    !!recordedLabel &&
    accepted.toLowerCase() !== recordedLabel.toLowerCase();

  // No accepted name at all: the status column carries the explanation.
  if (!accepted) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
        {recordedLabel ? (
          <span className="block text-xs italic text-deep-mocha-500 truncate">
            as{" "}
            <HighlightText
              text={recordedLabel}
              highlight={query}
              isMatched={isMatched}
            />
          </span>
        ) : null}
      </div>
    );
  }

  const isGenusOnly = specimen.accepted_rank === "genus";
  // Linked only when the record has a species page. A genus has none to open,
  // so the name stays plain text and the marker beside it says why.
  const href = speciesPageHref(specimen.species_key);

  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="italic whitespace-nowrap truncate">
        {href ? (
          <Link
            href={href}
            className="text-hunter-green-600 dark:text-hunter-green-400 hover:underline font-semibold"
          >
            <HighlightText
              text={accepted}
              highlight={query}
              isMatched={isMatched}
            />
          </Link>
        ) : (
          <HighlightText
            text={accepted}
            highlight={query}
            isMatched={isMatched}
          />
        )}
        {isGenusOnly ? (
          <span className="not-italic text-xs text-deep-mocha-500">
            {" "}
            genus only
          </span>
        ) : null}
      </span>
      {differs ? (
        // The query may have matched the recorded name rather than the
        // accepted one, which is why the highlight belongs on both lines.
        <span className="block text-xs italic text-deep-mocha-500 truncate">
          as{" "}
          <HighlightText
            text={recordedLabel}
            highlight={query}
            isMatched={isMatched}
          />
        </span>
      ) : null}
    </div>
  );
}

function renderCoordinateCell(
  lat: number | null | undefined,
  lon: number | null | undefined,
  matchedFields: string[],
) {
  const hasLat = lat !== null && lat !== undefined;
  const hasLon = lon !== null && lon !== undefined;
  if (!hasLat && !hasLon) {
    return (
      <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
    );
  }

  const isMatched =
    matchedFields.includes("lat") ||
    matchedFields.includes("lon") ||
    matchedFields.includes("coordinate");

  const text = `${hasLat ? lat!.toFixed(4) : "—"}, ${hasLon ? lon!.toFixed(4) : "—"}`;

  if (isMatched) {
    return (
      <mark className="bg-yellow-200 dark:bg-yellow-800/80 text-black dark:text-white px-1 rounded-xs">
        {text}
      </mark>
    );
  }

  return <span>{text}</span>;
}

/**
 * The catalog number, with the holding institution beneath it: its full name
 * linked to its website when public records give one, else the name or the
 * recorded code on its own.
 */
function renderSpecimenIdCell(specimen: SpecimenMetadata) {
  const {
    catalog_number: catalogNumber,
    institution_code: code,
    institution_name: name,
  } = specimen;
  if (!catalogNumber && !code) {
    return (
      <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
    );
  }
  const holder = name ?? code;
  const homepage = name ? safeWebUrl(specimen.institution_homepage) : null;
  const holderTitle =
    name && code && code !== name ? `${name} (${code})` : holder;
  return (
    <div className="flex flex-col gap-0.5 max-w-48">
      <span className="whitespace-nowrap">{catalogNumber ?? "—"}</span>
      {holder &&
        (homepage ? (
          <a
            href={homepage}
            target="_blank"
            rel="noopener noreferrer"
            title={holderTitle ?? undefined}
            aria-label={`${name} website`}
            className="truncate text-xs text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
          >
            {holder}
          </a>
        ) : (
          <span
            title={holderTitle ?? undefined}
            className="truncate text-xs text-deep-mocha-500 dark:text-deep-mocha-400"
          >
            {holder}
          </span>
        ))}
    </div>
  );
}

function SpecimenThumbnail({
  imgId,
  species,
  onClick,
}: {
  imgId: string | null | undefined;
  species: string | null | undefined;
  onClick?: () => void;
}) {
  const boxClasses =
    "relative h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-deep-mocha-100 dark:bg-deep-mocha-800";

  if (!imgId) {
    return (
      <div className={`${boxClasses} flex items-center justify-center`}>
        <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      title="Open full image"
      aria-label="Open full-size specimen image"
      className={`${boxClasses} transition-all hover:shadow-lg hover:ring-1 hover:ring-pacific-blue-600 focus:outline-none focus:ring-2 focus:ring-hunter-green-500`}
    >
      <Image
        src={imageUrlById(imgId, "thumbnail")}
        alt={
          species
            ? `Specimen image of ${species.replace(/_/g, " ")}`
            : "Specimen image"
        }
        fill
        sizes={`${SPECIMEN_THUMB_SIZE}px`}
        className="object-contain"
        unoptimized
      />
    </button>
  );
}

function DbSearch({
  query,
  initialField = "all",
}: {
  query: string;
  initialField?: string;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pageParam = searchParams.get("page") || "1";
  const initialPage = parseInt(pageParam, 10) || 1;

  const [results, setResults] = useState<DbResultItems[]>([]);
  const [specimens, setSpecimens] = useState<SpecimenMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState(initialField);
  const [page, setPage] = useState(initialPage);
  const [totalSpecimens, setTotalSpecimens] = useState(0);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchDatabase(query, field, page);
        setResults(response.results);
        setSpecimens(response.specimens);
        setTotalSpecimens(response.total_specimens);
        setLimit(response.limit);
      } catch (error) {
        setError("Failed to fetch search results");
      } finally {
        setLoading(false);
      }
    };

    if (query) {
      fetchResults();
    }
  }, [query, field, page]);

  const handleSearch = (newQuery: string, mode: string) => {
    setPage(1);
    const newUrl = `/search?q=${encodeURIComponent(newQuery)}&mode=${mode}&field=${encodeURIComponent(field)}&page=1`;
    router.push(newUrl, { scroll: false });
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    const newUrl = `/search?q=${encodeURIComponent(query)}&mode=text&field=${encodeURIComponent(field)}&page=${newPage}`;
    router.push(newUrl, { scroll: false });
  };

  if (error) {
    return <p className="text-burnt-peach-500">Error: {error}</p>;
  }

  return (
    <div className="items-center max-w-7xl w-full px-4 mx-auto">
      <BackLink />
      <div
        id="search-query"
        className="mb-12 mt-8 text-center flex flex-col items-center gap-4"
      >
        <div className="w-full max-w-2xl">
          <SearchForm
            mode="text"
            icon={FlaskConical}
            onSubmit={handleSearch}
            query={query}
            placeholder="Search database..."
          />
        </div>

        <div className="flex items-center gap-3 text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
          <label
            htmlFor="search-field-select"
            className="font-semibold tracking-wide uppercase text-xs text-deep-mocha-500 dark:text-deep-mocha-400"
          >
            Search by:
          </label>
          <SearchFieldSelect
            id="search-field-select"
            value={field}
            onChange={(newField) => {
              setField(newField);
              setPage(1);
              const newUrl = `/search?q=${encodeURIComponent(query)}&mode=text&field=${encodeURIComponent(newField)}&page=1`;
              router.push(newUrl, { scroll: false });
            }}
            groups={FIELD_GROUPS}
            className="w-56"
          />
        </div>
      </div>

      <div id="results-section" className="mt-2">
        <div className="mb-6 text-center">
          <h1 className="text-xl sm:text-4xl font-extrabold tracking-tight font-serif bg-linear-to-r from-hunter-green-500 via-pacific-blue-500 to-frozen-water-500 text-transparent bg-clip-text drop-shadow">
            Search Results
          </h1>
        </div>
        <DbSearchResults
          results={results}
          specimens={specimens}
          query={query}
          loading={loading}
          totalSpecimens={totalSpecimens}
          page={page}
          limit={limit}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  );
}

const SPECIES_PER_PAGE = 20;

function DbSearchResults({
  results,
  specimens,
  query,
  loading,
  totalSpecimens,
  page,
  limit,
  onPageChange,
}: {
  results: DbResultItems[];
  specimens: SpecimenMetadata[];
  query: string;
  loading: boolean;
  totalSpecimens: number;
  page: number;
  limit: number;
  onPageChange: (newPage: number) => void;
}) {
  const [speciesPage, setSpeciesPage] = useState(1);
  // index into `specimens` of the row whose thumbnail is open in the
  // full-image modal; reset whenever a new page/query loads new specimens.
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  useEffect(() => {
    setOpenIndex(null);
  }, [specimens]);
  const specimenImageIds = specimens.map((s) => s.img_id);
  const totalSpeciesPages = Math.ceil(results.length / SPECIES_PER_PAGE);
  const speciesStart = (speciesPage - 1) * SPECIES_PER_PAGE;
  const paginatedSpecies = results.slice(
    speciesStart,
    speciesStart + SPECIES_PER_PAGE,
  );

  if (query.trim() === "" && !loading) {
    return (
      <div className="text-center py-12">
        <p className="text-deep-mocha-500 dark:text-deep-mocha-400 font-medium">
          Please enter a search query.
        </p>
      </div>
    );
  }

  if (results.length === 0 && specimens.length === 0 && !loading) {
    return (
      <div className="text-center py-12">
        <p className="text-deep-mocha-500 dark:text-deep-mocha-400 font-medium">
          No results found for &ldquo;{query}&rdquo;. Please try a different
          query.
        </p>
      </div>
    );
  }

  return (
    <div>
      {loading ? (
        <div className="flex flex-col items-center mt-24">
          <ImageLoading size={240} msg="Loading results" />
        </div>
      ) : (
        <div className="flex flex-col gap-12 mt-5">
          {/* Top Section: Species Cards Grid */}
          {results.length > 0 && (
            <div>
              <div className="mb-4">
                <h2
                  id="species-results"
                  className="text-2xl font-bold tracking-tight text-deep-mocha-800 dark:text-deep-mocha-100 font-serif"
                >
                  Species pages containing query ({results.length})
                </h2>
                <Tips message="Click on an image card to navigate to the species detail page." />
              </div>
              <div className="grid grid-flow-row grid-cols-[repeat(auto-fill,160px)] gap-4">
                {paginatedSpecies.map((item, index) => (
                  <Suspense
                    key={speciesStart + index}
                    fallback={<div>Loading species...</div>}
                  >
                    <DbResultCard data={item} />
                  </Suspense>
                ))}
              </div>

              <PaginationControls
                currentPage={speciesPage}
                totalPages={totalSpeciesPages}
                totalItems={results.length}
                itemsPerPage={SPECIES_PER_PAGE}
                label="species"
                onPageChange={setSpeciesPage}
              />
            </div>
          )}
          {/* Bottom Section: Specimen Metadata Table */}
          {specimens.length > 0 && (
            <div>
              <div className="mb-4">
                <h2
                  id="specimen-results"
                  className="text-2xl font-bold tracking-tight text-deep-mocha-800 dark:text-deep-mocha-100 font-serif"
                >
                  Specimens matching query ({totalSpecimens})
                </h2>
                <Tips message="Species show the Catalogue of Life accepted name, with the name as recorded beneath it. Locality comes from the GBIF occurrence record, and the coordinate status is checked against GADM administrative boundaries. Click any status badge to see how it was decided." />
              </div>

              <div className="overflow-x-auto w-full rounded-2xl border border-deep-mocha-200 dark:border-deep-mocha-700/80 shadow-xs bg-white/40 dark:bg-deep-mocha-800/40 backdrop-blur-md">
                <table className="w-full text-left text-sm text-deep-mocha-700 dark:text-deep-mocha-300 border-collapse">
                  <thead className="bg-hunter-green-500/10 dark:bg-hunter-green-500/20 text-hunter-green-800 dark:text-hunter-green-300 font-semibold tracking-wider text-xs uppercase border-b border-deep-mocha-200 dark:border-deep-mocha-700">
                    <tr>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Image
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Species
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Taxon Status
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Family
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Specimen ID
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Sex
                      </th>
                      <th className="hidden xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        Life Stage
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Common Name
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        View
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Country
                      </th>
                      <th className="hidden lg:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        State / Province
                      </th>
                      <th className="hidden 2xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        County
                      </th>
                      <th className="hidden 2xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        Municipality
                      </th>
                      <th className="hidden xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        Locality
                      </th>
                      <th className="hidden 2xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        Verbatim Locality
                      </th>
                      {/* Was headed "Locality", which it never showed. */}
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Coordinates
                      </th>
                      <th className="px-4 py-3 font-semibold whitespace-nowrap">
                        Coord. Status
                      </th>
                      <th className="hidden xl:table-cell px-4 py-3 font-semibold whitespace-nowrap">
                        Source DB
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-deep-mocha-200/50 dark:divide-deep-mocha-700/50">
                    {specimens.map((specimen, idx) => {
                      const matched = specimen.matched_fields || [];
                      return (
                        <tr
                          key={specimen.img_id || idx}
                          className="hover:bg-hunter-green-50/50 dark:hover:bg-hunter-green-950/20 transition-colors"
                        >
                          <td className="px-4 py-2 align-middle">
                            <SpecimenThumbnail
                              imgId={specimen.img_id}
                              species={specimen.species}
                              onClick={() => setOpenIndex(idx)}
                            />
                          </td>
                          <td className="px-4 py-3 align-top font-medium max-w-56">
                            {renderTaxonCell(specimen, query)}
                          </td>
                          <td className="px-4 py-3 align-top">
                            <TaxonStatusBadge
                              update={{
                                updateStatus: specimen.update_status as
                                  | "MATCHED"
                                  | "AMBIGUOUS"
                                  | "UNMATCHED"
                                  | null,
                                matchMethod: specimen.match_method,
                              }}
                              compact
                            />
                          </td>
                          <td className="px-4 py-3 align-top capitalize">
                            <HighlightText
                              text={specimen.family}
                              highlight={query}
                              isMatched={matched.includes("family")}
                            />
                          </td>
                          <td className="px-4 py-3 align-top">
                            {renderSpecimenIdCell(specimen)}
                          </td>
                          <td className="px-4 py-3 align-middle capitalize">
                            <HighlightText
                              text={specimen.sex}
                              highlight={query}
                              isMatched={matched.includes("sex")}
                            />
                          </td>
                          <td className="hidden xl:table-cell px-4 py-3 align-top capitalize">
                            <HighlightText
                              text={specimen.life_stage}
                              highlight={query}
                              isMatched={matched.includes("life_stage")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.common_name}
                              highlight={query}
                              isMatched={matched.includes("common_name")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle capitalize">
                            <HighlightText
                              text={specimen.class_dv}
                              highlight={query}
                              isMatched={matched.includes("class_dv")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            <HighlightText
                              text={specimen.country ?? specimen.country_code}
                              highlight={query}
                              isMatched={matched.includes("country")}
                            />
                          </td>
                          <td className="hidden lg:table-cell px-4 py-3 align-top">
                            <HighlightText
                              text={specimen.state_province}
                              highlight={query}
                              isMatched={matched.includes("state_province")}
                            />
                          </td>
                          <td className="hidden 2xl:table-cell px-4 py-3 align-top">
                            <HighlightText
                              text={specimen.county}
                              highlight={query}
                              isMatched={matched.includes("county")}
                            />
                          </td>
                          <td className="hidden 2xl:table-cell px-4 py-3 align-top">
                            <HighlightText
                              text={specimen.municipality}
                              highlight={query}
                              isMatched={matched.includes("municipality")}
                            />
                          </td>
                          {/* Free text, and long: truncated with the whole
                              string on the title, or one verbose record
                              stretches every column. */}
                          <td
                            className="hidden xl:table-cell px-4 py-3 align-top max-w-48 truncate"
                            title={specimen.locality ?? undefined}
                          >
                            <HighlightText
                              text={specimen.locality}
                              highlight={query}
                              isMatched={matched.includes("locality")}
                            />
                          </td>
                          <td
                            className="hidden 2xl:table-cell px-4 py-3 align-top max-w-48 truncate"
                            title={specimen.verbatim_locality ?? undefined}
                          >
                            <HighlightText
                              text={specimen.verbatim_locality}
                              highlight={query}
                              isMatched={matched.includes("verbatim_locality")}
                            />
                          </td>
                          <td className="px-4 py-3 align-middle">
                            {renderCoordinateCell(
                              specimen.lat,
                              specimen.lon,
                              matched,
                            )}
                          </td>
                          <td className="px-4 py-3 align-top">
                            <CoordinateStatusBadge
                              validation={{
                                validationStatus:
                                  specimen.validation_status as CoordinateValidationStatusCode | null,
                              }}
                              compact
                            />
                          </td>
                          <td className="hidden xl:table-cell px-4 py-3 align-top uppercase">
                            <HighlightText
                              text={specimen.source_db}
                              highlight={query}
                              isMatched={matched.includes("source_db")}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <PaginationControls
                currentPage={page}
                totalPages={Math.ceil(totalSpecimens / limit)}
                totalItems={totalSpecimens}
                itemsPerPage={limit}
                label="specimens"
                onPageChange={onPageChange}
              />

              <ColAttribution leadingText="Taxonomy source:" />
              <GadmAttribution leadingText="Boundary source:" />
              {/* One link for the whole table: the status columns above
                  carry a hover hint per row, and this is the page that
                  explains what those verdicts are. */}
              <p className="text-xs text-deep-mocha-500 mt-2">
                <Link
                  href="/resources#taxonomy-matching"
                  className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
                >
                  How taxonomy and coordinate matching work
                </Link>
              </p>
            </div>
          )}
        </div>
      )}

      <SpecimenImageModal
        ids={specimenImageIds}
        openIndex={openIndex}
        onOpenIndexChange={setOpenIndex}
      />
    </div>
  );
}

function DbResultCard({ data }: { data: DbResultItems }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchImage = async () => {
      try {
        const url = await fetchSpeciesThumbnail(data.species);
        if (mounted) setImageUrl(url);
      } catch (error) {
        console.error("Error fetching image for DbResultCard:", error);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchImage();
    return () => {
      mounted = false;
    };
  }, [data.species]);

  return (
    <div className="bg-deep-mocha-200 dark:bg-deep-mocha-700 rounded-2xl p-4 flex flex-col items-center justify-center text-center w-[160px] min-h-[160px]">
      {loading ? (
        <ImageLoading size={IMAGE_SIZE} />
      ) : (
        <MaybeSpeciesLink
          speciesKey={data.species_key}
          className="flex flex-col items-center justify-between h-full w-full gap-2"
        >
          <div className="flex flex-1 items-center justify-center w-full">
            <div className="relative aspect-square w-full max-w-32">
              <Image
              src={imageUrl || `/api/image/${data.species}`}
              alt={`Image of ${data.species}`}
              fill
              sizes={`${IMAGE_SIZE}px`}
              className="object-contain"
              unoptimized
              />
            </div>
          </div>

          <h2 className="text-sm truncate text-center text-deep-mocha-400 italic w-full">
            {cleanSpeciesName(data.species)}
          </h2>
          <p className="text-xs text-deep-mocha-500 w-full">
            Matched:{" "}
            {data.matched_fields
              .map((field) => field.replace(/_/g, " "))
              .join(", ")}
          </p>
        </MaybeSpeciesLink>
      )}
    </div>
  );
}

export { DbSearch };
