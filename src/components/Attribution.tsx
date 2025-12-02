const gbifURL = "https://www.gbif.org/";
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
    <p className={`text-xs text-gray-500 mt-2 ${isLarge ? "text-lg" : ""}`}>
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

export function LepTraitsAttribution({
  isLarge = false,
}: {
  isLarge?: boolean;
}) {
  return (
    <p className={`text-gray-500 mt-2 ${isLarge ? "text-lg" : "text-xs"}`}>
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
    <div className="text-md text-gray-600 dark:text-gray-400 border border-teal-300/30 bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-4 rounded-xl mt-8">
      <p>
        The trait data is sourced from the{" "}
        <a
          href={lepTraitURL}
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-teal-300"
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
          className="underline hover:text-teal-300"
        >
          https://doi.org/10.1038/s41597-022-01473-5
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
    <p className={`text-gray-500 mt-2 ${isLarge ? "text-md" : "text-xs"}`}>
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

export function CrossRefAttribution({
  leadingText = "Source: ",
  isLarge = false,
}: {
  leadingText?: string;
  isLarge?: boolean;
}) {
  return (
    <p className={`text-gray-500 mt-2 ${isLarge ? "text-md" : "text-xs"}`}>
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
