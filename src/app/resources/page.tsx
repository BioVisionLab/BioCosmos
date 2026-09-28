import {
  ColDataSourceInfo,
  CrossRefLink,
  GadmAttribution,
  GbifDataSourceInfo,
  LepTraitDataSourceInfo,
  NcbiDataSourceInfo,
} from "@/components/Attribution";
import { statusLabel, humanizeCode, toneForStatus } from "@/lib/colTaxonomy";
import {
  coordinateStatusLabel,
  toneForCoordinateStatus,
} from "@/lib/geoValidation";
import {
  ADM1_CHECK_ROWS,
  COORDINATE_CHECK_ROWS,
  COUNTRY_CHECK_ROWS,
  MATCH_METHOD_ROWS,
  REASON_CODE_ROWS,
  UPDATE_STATUS_ROWS,
  VALIDATION_STATUS_ROWS,
} from "@/lib/matchingDocs";
import CodeTable from "./CodeTable";
import BackLink from "@/components/BackLink";
import Link from "next/link";

const COL_URL = "https://www.catalogueoflife.org/";
const COL_TAXONOMY_URL = "https://github.com/hhandika/col-taxonomy";
const GADM_URL = "https://gadm.org/";

/**
 * The caveat both matching sections carry.
 *
 * Every verdict on this site comes from an automated check, and the two
 * sections have the same thing to say about that: a check that did not
 * resolve is a statement about the check, not about the specimen, and the
 * data as recorded is always kept so a reader can compare.
 */
function AutomatedCheckNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-l-4 border-pacific-blue-400/60 bg-pacific-blue-500/5 dark:bg-pacific-blue-400/10 rounded-r-lg py-3 pl-4 pr-4 text-sm">
      {children}
    </div>
  );
}

export default function ResourcesPage() {
  return (
    // Not a <main>: Layout already renders one, and this was nested inside it
    // — invalid, and its `p-8` sat on top of the shell's own `px-4`, which left
    // a 375px phone about 279px of content to read in. Same width as the
    // Collections page so the content pages line up.
    <div className="w-full max-w-7xl 2xl:max-w-352 mx-auto py-4">
      <BackLink />
      <h1 className="text-3xl font-bold mb-4">
        Resources and Data Usage Attribution
      </h1>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Primary Data</h2>
        <p>
          Primary data consists of butterfly images and their associated
          metadata. These datasets are courtesy of{" "}
          <Link
            href="/collections/providers"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            museum providers
          </Link>
          . We downloaded the metadata from data aggregators (mainly{" "}
          <a
            href="https://www.gbif.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            GBIF
          </a>
          ,{" "}
          <a
            href="https://idigbio.gbif.us/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            iDigBio
          </a>
          ,{" "}
          <a
            href="https://ecdysis.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            Ecdysis
          </a>
          , and{" "}
          <a
            href="https://scan-all-bugs.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            SCANBUGS
          </a>
          ). The images were downloaded directly from the institutions through
          the links provided in the metadata.
        </p>
      </section>
      <section
        id="taxonomy-matching"
        className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed scroll-mt-24"
      >
        <h2 className="text-2xl font-semibold">Taxonomy Matching</h2>
        <p>
          The scientific names in museum records may be outdated, misspelled, or
          since synonymized. We update the recorded names to match the most
          current taxonomy in a{" "}
          <a
            href={COL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            Catalogue of Life
          </a>{" "}
          release. This is done using automated methods, with no manual curation
          step. We reserve the original recorded name and display it alongside
          the accepted name when they differ, so you can compare them and judge
          for yourself.
        </p>
        <p>
          The pipeline normalized the names first: underscores become spaces,
          whitespace is collapsed, case is folded, and parenthetical subgenera
          are dropped. We then attempt to match the normalized name against the
          Catalogue of Life release and use the categories below to describe the
          outcome of the match.
        </p>

        <h3 className="text-lg font-semibold pt-2">Matching Categories</h3>
        <p>
          Each name ends in one of three states, shown as a badge on the
          specimen:
        </p>
        <CodeTable
          head={["Outcome", "Meaning"]}
          rows={UPDATE_STATUS_ROWS.map((row) => ({
            key: row.code,
            label: statusLabel(row.code),
            tone: toneForStatus(row.code),
            description: row.description,
          }))}
        />

        <h3 className="text-lg font-semibold pt-2">How a match is made</h3>
        <p>
          Candidates are identified using seven methods below and ranked by
          score. Spelling or fuzzy matches are accepted only when unique or
          clearly outperform the runner-up. Otherwise, the result is ambiguous.
        </p>
        <CodeTable
          head={["Method", "Rule"]}
          rows={MATCH_METHOD_ROWS.map((row) => ({
            key: row.code,
            label: humanizeCode(row.code),
            description: row.description,
          }))}
        />

        <p className="text-sm">
          The full specification — normalization, candidate methods, scoring,
          the rank cascade, and the ambiguity rules — is published with the{" "}
          <a
            href={COL_TAXONOMY_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            col-taxonomy
          </a>{" "}
          project.
        </p>
        <ColDataSourceInfo />
      </section>

      <section
        id="coordinate-matching"
        className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed scroll-mt-24"
      >
        <h2 className="text-2xl font-semibold">Coordinate Matching</h2>

        <p>
          A specimen&apos;s origin may be georeferenced in two ways: as a
          written locality (country, state or province, and locality) and as
          geographic coordinates (latitude and longitude). These independent
          sources of information may disagree because of transcription errors,
          reversed coordinate signs, or coordinates assigned later using a
          different gazetteer. We automatically check every coordinate against
          its associated written locality.
        </p>

        <AutomatedCheckNote>
          Coordinate validation uses fixed geographic boundaries and may produce
          mismatches due to border proximity, administrative changes, or
          differences in locality precision.{" "}
          <strong className="font-semibold">
            A mismatch warrants review but does not necessarily indicate an
            error.
          </strong>{" "}
          The original locality and coordinates are preserved alongside the
          region identified by the automated check.
        </AutomatedCheckNote>

        <p>
          Coordinates are validated and compared against{" "}
          <a
            href={GADM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            GADM
          </a>{" "}
          administrative boundaries. The identified region is compared with the
          recorded country and state/province. A region is assigned only when
          exactly one boundary matches. Coordinates outside all boundaries or
          overlapping multiple boundaries fall into other categories described
          below.
        </p>

        <CodeTable
          head={["Verdict", "Meaning"]}
          rows={VALIDATION_STATUS_ROWS.map((row) => ({
            key: row.code,
            label: coordinateStatusLabel(row.code),
            tone: toneForCoordinateStatus(row.code),
            description: row.description,
          }))}
        />

        <details className="pt-2">
          <summary className="cursor-pointer text-sm font-medium hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300">
            The component checks behind each category are described in the
            tables below. Click to expand.
          </summary>

          <div className="mt-4 space-y-6">
            <div className="space-y-2">
              <h4 className="font-medium">Coordinate</h4>

              <CodeTable
                head={["Check", "Meaning"]}
                rows={COORDINATE_CHECK_ROWS.map((row) => ({
                  key: row.code,
                  label: humanizeCode(row.code),
                  description: row.description,
                }))}
              />
            </div>

            <div className="space-y-2">
              <h4 className="font-medium">Country</h4>

              <CodeTable
                head={["Check", "Meaning"]}
                rows={COUNTRY_CHECK_ROWS.map((row) => ({
                  key: row.code,
                  label: humanizeCode(row.code),
                  description: row.description,
                }))}
              />
            </div>

            <div className="space-y-2">
              <h4 className="font-medium">State or province</h4>

              <CodeTable
                head={["Check", "Meaning"]}
                rows={ADM1_CHECK_ROWS.map((row) => ({
                  key: row.code,
                  label: humanizeCode(row.code),
                  description: row.description,
                }))}
              />
            </div>
          </div>
        </details>

        <GadmAttribution />
      </section>

      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Real-Time Occurrence Data</h2>

        <p>
          In addition to the primary collection data, real-time occurrence
          records are displayed in the species overview section. These records
          are retrieved directly from GBIF using the species name.
        </p>

        <GbifDataSourceInfo />
      </section>

      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Trait Datasets</h2>

        <LepTraitDataSourceInfo />
      </section>

      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Genetic Data</h2>

        <NcbiDataSourceInfo />
      </section>

      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Wikipedia</h2>

        <p>
          We use{" "}
          <a
            href="https://en.wikipedia.org/wiki/Main_Page"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            Wikipedia
          </a>{" "}
          as a supplementary source of species information. Its content is
          subject to Wikipedia&apos;s{" "}
          <a
            href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            licensing requirements
          </a>
          .
        </p>
      </section>

      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Literature</h2>
        <p>
          The literature data is obtained from <CrossRefLink />. BioCosmos
          filter the data to get the most relevant information for literature
          lists.
        </p>
      </section>
    </div>
  );
}
