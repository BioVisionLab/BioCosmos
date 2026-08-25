function toTitleCase(str: string) {
  return str
    .toLowerCase()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function toSentenceCase(str: string) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function toAuthorNameCase(str: string) {
  return str
    .split(" ")
    .map((word) => {
      if (word.includes("-")) {
        return word
          .split("-")
          .map(
            (part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase()
          )
          .join("-");
      } else {
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
      }
    })
    .join(" ");
}

function decodeHtmlEntities(str: string): string {
  if (!str) return "";
  return str
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;|&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(Number(dec)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) =>
      String.fromCharCode(parseInt(hex, 16))
    );
}

function formatNumberToLocaleString(num: number): string {
  return num.toLocaleString("en-US");
}

function toSpeciesName(raw: string): string {
  const parts = raw
    .trim()
    .toLowerCase()
    .split("_")
    .filter((p) => p.length > 0);
  if (parts.length === 0) return raw;
  parts[0] = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  return parts.join(" ");
}

export {
  toTitleCase,
  toSentenceCase,
  toSpeciesName,
  decodeHtmlEntities,
  toAuthorNameCase,
  formatNumberToLocaleString,
};
