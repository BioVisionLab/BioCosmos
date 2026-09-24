import { COL_RELEASE } from "@/lib/colTaxonomy";

const gbifURL = "https://www.gbif.org/";
const colURL = "https://www.catalogueoflife.org/";
const lepTraitURL = "https://github.com/RiesLabGU/LepTraits";
const lepTraitPublication = "https://doi.org/10.1038/s41597-022-01473-5";

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
        className="underline hover:text-blue-700"
      >
        GBIF
      </a>
    </p>
  );
}

export function GbifDataSourceInfo() {
  return (
    <div className="text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-gradient-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2">
      <p>
        The occurrence data is sourced from{" "}
        <a
          href={gbifURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
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
        className="underline hover:text-blue-700"
      >
        LepTraits
      </a>
      <span> (</span>
      <a
        href={lepTraitPublication}
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-blue-700"
      >
        Shirey <em>et al.</em>, 2022
      </a>
      <span>)</span>
    </p>
  );
}

export function LepTraitDataSourceInfo() {
  return (
    <div className="text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-gradient-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2">
      <p>
        The trait data is sourced from the{" "}
        <a
          href={lepTraitURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
        >
          LepTraits database
        </a>
        . For more information on the database and its methodology, please refer
        to the original publication:
      </p>
      <p className="mt-2">
        Shirey, V., Larsen, E., Doherty, A., Kim, C.A., Al-Sulaiman, F.T.,
        Hinolan, J.D., Itliong, M.G.A., Naive, M.A.K., Ku, M., Belitz, M. and
        Jeschke, G. (2022). LepTraits 1.0: A globally comprehensive dataset of
        butterfly traits. Scientific Data, 9(1), p.382.{" "}
        <a
          href={lepTraitPublication}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
        >
          https://doi.org/10.1038/s41597-022-01473-5
        </a>
      </p>
    </div>
  );
}

/**
 * The Genetics counterpart of `LepTraitDataSourceInfo`, in the same panel, so
 * the two sources on the Biology tab are credited the same way.
 */
export function NcbiGeneDataSourceInfo({
  speciesName,
}: {
  speciesName: string;
}) {
  const geneSearch = `https://www.ncbi.nlm.nih.gov/gene/?term=${encodeURIComponent(
    `"${speciesName}"[Organism]`,
  )}`;
  return (
    <div className="text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2">
      <p>
        Gene counts are fetched live from the{" "}
        <a
          href="https://www.ncbi.nlm.nih.gov/datasets/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
        >
          NCBI Datasets
        </a>{" "}
        gene service. They count the genes annotated for this species in NCBI
        Gene, which depends on whether its genome has been sequenced and
        annotated.
      </p>
      <p className="mt-2">
        <a
          href={geneSearch}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
        >
          Browse the gene records for <i>{speciesName}</i> in NCBI Gene
        </a>
      </p>
    </div>
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
        className="underline hover:text-blue-700"
      >
        NCBI
      </a>
    </p>
  );
}

export function NcbiDataSourceInfo() {
  return (
    <div className="text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-gradient-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2">
      <p>
        Genetic data is sourced from{" "}
        <a
          href="https://www.ncbi.nlm.nih.gov/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
        >
          the United States National Center for Biotechnology Information (NCBI)
        </a>
        . BioCosmos queries realtime data using{" "}
        <a
          href="https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
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
        className="underline hover:text-blue-700"
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
      className="underline hover:text-blue-700"
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
      className="underline hover:text-blue-700"
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
        className="underline hover:text-blue-700"
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
    <div className="text-base text-deep-mocha-600 dark:text-deep-mocha-400 border border-pacific-blue-300/30 bg-gradient-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-xl mt-2">
      <p>
        Taxonomy is reconciled against{" "}
        <a
          href={colURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-pacific-blue-300"
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
        className="underline hover:text-blue-700"
      >
        GADM
      </a>
    </p>
  );
}
