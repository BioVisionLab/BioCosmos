const gbifURL = "https://www.gbif.org/";
const lepTraitURL = "https://github.com/RiesLabGU/LepTraitss";
const lepTraitPublication = "https://doi.org/10.1038/s41597-022-01473-5";

export function GbifAttribution({
  leadingText = "Source: ",
}: {
  leadingText?: string;
}) {
  return (
    <p className="text-xs text-gray-500 mt-2">
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

export function LepTraitsAttribution() {
  return (
    <p className="text-xs text-gray-500 mt-2">
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
