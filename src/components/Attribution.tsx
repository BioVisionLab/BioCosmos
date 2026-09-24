import { COL_RELEASE } from "@/lib/colTaxonomy";
import Callout from "@/components/Callout";
import CopyButton from "@/components/CopyButton";
import Note from "@/components/Note";
import { ArrowUpRight, ExternalLink, Quote } from "lucide-react";
import type { ReactNode } from "react";

const gbifURL = "https://www.gbif.org/";
const colURL = "https://www.catalogueoflife.org/";
const lepTraitURL = "https://github.com/RiesLabGU/LepTraits";
const lepTraitPublication = "https://doi.org/10.1038/s41597-022-01473-5";
const lepTraitCitation =
  "Shirey, V., Larsen, E., Doherty, A., Kim, C. A., Al-Sulaiman, F. T., " +
  "Hinolan, J. D., Itliong, M. G. A., Naive, M. A. K., Ku, M., Belitz, M., " +
  "& Jeschke, G. (2022). LepTraits 1.0: A globally comprehensive dataset of " +
  `butterfly traits. Scientific Data, 9, 382. ${lepTraitPublication}`;

/** The shared panel for data-source info and notes, so they read as a set. */
const infoPanelClass =
  "text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2";

/**
 * A link inside an info panel. Coloured as well as underlined so it stands
 * apart from the panel text: pacific-blue-700 is 5.3:1 on the light panel and
 * pacific-blue-300 8.5:1 on the dark one, and the hover steps keep that.
 */
const panelLinkClass =
  "text-pacific-blue-700 underline decoration-pacific-blue-700/40 underline-offset-2 hover:text-pacific-blue-800 hover:decoration-current dark:text-pacific-blue-300 dark:decoration-pacific-blue-300/40 dark:hover:text-pacific-blue-200";

function PanelLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={panelLinkClass}
    >
      {children}
    </a>
  );
}

/** An outbound link on its own line in a callout, marked as leaving the site. */
function PanelLinkRow({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <li>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={`${panelLinkClass} inline-flex items-start gap-1`}
      >
        <span>{children}</span>
        <ArrowUpRight aria-hidden="true" className="mt-px size-3 shrink-0" />
      </a>
    </li>
  );
}

export function GbifAttribution({
  leadingText = "Source: ",
  isLarge = false,
}: {
  leadingText?: string;
  isLarge?: boolean;
}) {
  return (
    <p
      className={`text-xs text-deep-mocha-500 mt-2 ${isLarge ? "text-lg" : ""}`}
    >
      {leadingText}{" "}
      <a
        href={gbifURL}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        GBIF
      </a>
    </p>
  );
}

export function GbifDataSourceInfo() {
  return (
    <div className={infoPanelClass}>
      <p>
        The occurrence data is sourced from{" "}
        <a
          href={gbifURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
        >
          the Global Biodiversity Information Facility (GBIF)
        </a>
        .
      </p>
    </div>
  );
}

export function LepTraitsAttribution({
  isLarge = false,
}: {
  isLarge?: boolean;
}) {
  return (
    <p
      className={`text-deep-mocha-500 mt-3 mb-1 ml-1 ${isLarge ? "text-lg" : "text-xs"}`}
    >
      Source:{" "}
      <a
        href={lepTraitURL}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        LepTraits
      </a>
      <span> (</span>
      <a
        href={lepTraitPublication}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        Shirey <em>et al.</em>, 2022
      </a>
      <span>)</span>
    </p>
  );
}

/** Where the trait data come from, with the publication to cite. */
export function LepTraitDataSourceInfo() {
  return (
    <Callout icon={Quote} label="Data source">
      <p>
        Trait data come from the{" "}
        <PanelLink href={lepTraitURL}>LepTraits database</PanelLink>. For its
        sources and methods, see the original publication:
      </p>
      <div className="pt-2">
        <div className="space-y-1 border-l-2 border-deep-mocha-600/40 pl-2">
          <p>
            Shirey, V., Larsen, E., Doherty, A., Kim, C. A., Al-Sulaiman, F. T.,
            Hinolan, J. D., Itliong, M. G. A., Naive, M. A. K., Ku, M., Belitz,
            M., &amp; Jeschke, G. (2022). LepTraits 1.0: A globally
            comprehensive dataset of butterfly traits. <i>Scientific Data</i>,{" "}
            <i>9</i>, 382.{" "}
            <PanelLink href={lepTraitPublication}>
              doi:10.1038/s41597-022-01473-5
            </PanelLink>
          </p>
          <CopyButton text={lepTraitCitation} label="Copy citation" />
        </div>
      </div>
    </Callout>
  );
}

export function NcbiGeneDataNote() {
  return (
    <Note>
      <ul className="list-disc space-y-1 pl-4">
        <li>
          The genome shown is the NCBI designated species&apos; reference. If
          there is none designated, it will be from the most complete assembly.
        </li>
        <li>Gene counts depend on whether that genome has been annotated.</li>
        <li>
          Mitochondrial counts are GenBank nucleotide records filed as
          mitochondrial for this species or its subspecies.
        </li>
        <li>Counts are refreshed weekly.</li>
      </ul>
    </Note>
  );
}

/**
 * Where the Genetics tab's data come from, with the species' records in NCBI
 * for reading past the summary.
 */
export function NcbiGeneDataSourceInfo({
  speciesName,
}: {
  speciesName: string;
}) {
  const name = speciesName.replace(/_/g, " ");
  const geneSearch = `https://www.ncbi.nlm.nih.gov/gene/?term=${encodeURIComponent(
    `"${name}"[Organism]`,
  )}`;
  const mitoSearch = `https://www.ncbi.nlm.nih.gov/nuccore/?term=${encodeURIComponent(
    `"${name}"[Organism:noexp] AND mitochondrion[filter]`,
  )}`;
  return (
    <Callout icon={ExternalLink} label="Data source">
      <p>
        Genome assemblies, annotated gene counts and reference mitogenomes come
        from{" "}
        <PanelLink href="https://www.ncbi.nlm.nih.gov/datasets/">
          NCBI Datasets
        </PanelLink>
        ; mitochondrial sequence counts come from{" "}
        <PanelLink href="https://www.ncbi.nlm.nih.gov/books/NBK25501/">
          NCBI E-utilities
        </PanelLink>
        .
      </p>
      <ul className="space-y-1">
        <PanelLinkRow href={geneSearch}>
          Gene records for <i>{name}</i> in NCBI Gene
        </PanelLinkRow>
        <PanelLinkRow href={mitoSearch}>
          Mitochondrial sequences for <i>{name}</i> in NCBI Nucleotide
        </PanelLinkRow>
      </ul>
    </Callout>
  );
}

export function NcbiAttribution({
  leadingText = "Source: ",
  isLarge = false,
}: {
  leadingText?: string;
  isLarge?: boolean;
}) {
  return (
    <p
      className={`text-deep-mocha-500 mt-2 ${isLarge ? "text-base" : "text-xs"}`}
    >
      {leadingText}{" "}
      <a
        href="https://www.ncbi.nlm.nih.gov/"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        NCBI
      </a>
    </p>
  );
}

export function NcbiDataSourceInfo() {
  return (
    <div className={infoPanelClass}>
      <p>
        Genetic data is sourced from{" "}
        <a
          href="https://www.ncbi.nlm.nih.gov/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
        >
          the United States National Center for Biotechnology Information (NCBI)
        </a>
        . BioCosmos queries realtime data using{" "}
        <a
          href="https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
        >
          NCBI Datasets API
        </a>
        . It includes only genes that have been sequenced for the queried
        species.
      </p>
    </div>
  );
}

export function CrossRefAttribution({
  leadingText = "Source: ",
  isLarge = false,
}: {
  leadingText?: string;
  isLarge?: boolean;
}) {
  return (
    <p
      className={`text-deep-mocha-500 mt-2 ${isLarge ? "text-base" : "text-xs"}`}
    >
      {leadingText}{" "}
      <a
        href="https://www.crossref.org/"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        CrossRef
      </a>
    </p>
  );
}

export function CrossRefLink() {
  return (
    <a
      href="https://www.crossref.org/"
      target="_blank"
      rel="noopener noreferrer"
      className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
    >
      CrossRef
    </a>
  );
}

export function NcbiLink() {
  return (
    <a
      href="https://www.ncbi.nlm.nih.gov/"
      target="_blank"
      rel="noopener noreferrer"
      className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
    >
      NCBI
    </a>
  );
}

/**
 * @param release The Catalogue of Life release, named so a reader can tell
 *   which backbone produced the classification above it. Defaults to the one
 *   constant the whole site reads; pass `null` only where the release is
 *   already stated nearby.
 */
export function ColAttribution({
  leadingText = "Source: ",
  isLarge = false,
  release = COL_RELEASE,
}: {
  leadingText?: string;
  isLarge?: boolean;
  release?: string | null;
}) {
  return (
    <p
      className={`text-xs text-deep-mocha-500 mt-2 ${isLarge ? "text-lg" : ""}`}
    >
      {leadingText}{" "}
      <a
        href={colURL}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        Catalogue of Life
      </a>
      {release ? <span className="whitespace-nowrap"> ({release})</span> : null}
    </p>
  );
}

export function ColDataSourceInfo({
  release = COL_RELEASE,
}: {
  release?: string | null;
}) {
  return (
    <div className={infoPanelClass}>
      <p>
        Taxonomy is reconciled against{" "}
        <a
          href={colURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
        >
          the Catalogue of Life
        </a>
        {release ? ` (${release})` : ""}. Each recorded name is matched to an
        accepted Catalogue of Life usage, and the evidence behind that match is
        shown alongside every specimen, so a name that has since been
        synonymized or corrected can be seen for what it is.
      </p>
    </div>
  );
}

const gadmURL = "https://gadm.org/";

export function GadmAttribution({
  leadingText = "Source: ",
  isLarge = false,
}: {
  leadingText?: string;
  isLarge?: boolean;
}) {
  return (
    <p
      className={`text-xs text-deep-mocha-500 mt-2 ${isLarge ? "text-lg" : ""}`}
    >
      {leadingText}{" "}
      <a
        href={gadmURL}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
      >
        GADM
      </a>
    </p>
  );
}
