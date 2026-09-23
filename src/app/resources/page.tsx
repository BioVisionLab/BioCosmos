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
    <div className="w-full max-w-7xl 2xl:max-w-[88rem] mx-auto py-4">
      <BackLink />
      <h1 className="text-3xl font-bold mb-4">
        Resources and Data Usage Attribution
      </h1>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Primary Data</h2>
        <p>
          Primary data consists of butterfly images and their associated
          metadata. These datasets are courtesy of museum providers and our
          research collaborators. We downloaded the metadata from data
          agregators (mainly{" "}
          <a
            href="https://www.gbif.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            GBIF
          </a>
          ,{" "}
          <a
            href="https://idigbio.gbif.us/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            iDigBio
          </a>
          ,{" "}
          <a
            href="https://ecdysis.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            Ecdysis
          </a>
          , and{" "}
          <a
            href="https://scan-all-bugs.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
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
          Museum records carry the name a specimen was filed under, which may
          be decades old, misspelled, or since synonymized. Every recorded
          name on this site is therefore matched automatically against a{" "}
          <a
            href={COL_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            Catalogue of Life
          </a>{" "}
          release, across the whole collection and with no manual curation
          step.
        </p>
        <AutomatedCheckNote>
          This match is made by software, not by a curator, and it does not
          always succeed. A name can go unmatched or ambiguous because the
          Catalogue of Life release does not cover it yet, because the
          recorded family conflicts with the recorded name, or simply
          because two accepted taxa are equally good candidates.{" "}
          <strong className="font-semibold">
            An outcome other than &ldquo;matched&rdquo; says the check could
            not decide — not that the record is wrong.
          </strong>{" "}
          Nothing is overwritten: the name exactly as the institution entered
          it is kept and shown beside the accepted name, along with the
          method and the runner-up candidates, so you can compare them and
          judge for yourself.
        </AutomatedCheckNote>
        <p>
          Names are normalized first — underscores become spaces, whitespace
          is collapsed, case is folded, and parenthetical subgenera are
          dropped. Matching then cascades from species to subspecies to
          genus, and a match made at a coarser rank says so. A name recorded
          at some other rank, or one that cannot be read as a binomial, is
          not matched at all and carries a reason instead.
        </p>

        <h3 className="text-lg font-semibold pt-2">Outcome</h3>
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
          Candidates are gathered by seven methods and scored; the strongest
          is listed first. A spelling or fuzzy match only counts as matched
          when it is the sole candidate, or when it beats the runner-up by a
          clear scoring margin — otherwise the result is ambiguous rather
          than a guess.
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
          A method shown as <em>Subspecies ·</em> or <em>Genus ·</em> means
          the species-rank pass found nothing and the match was made at that
          coarser rank instead.
        </p>

        <h3 className="text-lg font-semibold pt-2">
          Why a name was not matched
        </h3>
        <CodeTable
          head={["Reason", "Meaning"]}
          rows={REASON_CODE_ROWS.map((row) => ({
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
            className="underline hover:text-blue-700"
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
          A specimen records its origin twice: once in words (country, state
          or province, locality) and once as a latitude and longitude. Those
          are two independent claims, and they can disagree — a transcription
          error, a swapped sign, or a coordinate added later from a different
          gazetteer. Every coordinate on this site is checked automatically
          against the locality written beside it.
        </p>
        <AutomatedCheckNote>
          This check is made by software against a fixed set of boundaries,
          and a disagreement is not by itself an error. A coordinate on a
          coastline or a national border can fall just outside the polygon
          it belongs to; a province may have been renamed or subdivided since
          the specimen was catalogued; a locality may have been recorded at
          country resolution while the coordinate is precise.{" "}
          <strong className="font-semibold">
            A mismatch is a prompt to look, not a verdict that the record is
            wrong.
          </strong>{" "}
          Both claims are preserved and displayed as recorded — the written
          locality and the coordinate — so you can compare them against the
          region the check derived.
        </AutomatedCheckNote>
        <p>
          The coordinate is parsed and range-checked, then tested against{" "}
          <a
            href={GADM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            GADM
          </a>{" "}
          administrative boundaries to find which region it actually falls
          in. That region is then compared with the country and state or
          province the record wrote down. A region is only reported when
          exactly one matched, so &ldquo;outside every boundary&rdquo; and
          &ldquo;where several regions meet&rdquo; stay distinct outcomes
          rather than both reading as a blank.
        </p>

        <h3 className="text-lg font-semibold pt-2">Verdict</h3>
        <p>
          The checks are applied in the order below and the first one that
          applies is the verdict, so a record whose country <em>and</em>{" "}
          state both disagree is reported as a country mismatch.
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
            The component checks behind each verdict
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

        <p className="text-sm">
          Coordinate validation runs offline against a fixed GADM release and
          is recorded per specimen, so a verdict shown here always refers to
          the boundary data it was computed from.
        </p>
        <GadmAttribution />
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Realtime Occurrence Data</h2>
        <p>
          In addition to the primary data, we show realtime occurrence data in
          the species overview section. This data is queried directly from GBIF
          using the species name.
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
            className="underline hover:text-blue-700"
          >
            Wikipedia
          </a>{" "}
          as a supplementary source of information for the species. See content{" "}
          <a
            href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            license
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
