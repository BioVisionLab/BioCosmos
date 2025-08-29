const gbifURL = "https://www.gbif.org/";

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
