// ---------- INTERFACES ----------
// Defines the structure for a piece of parsed content.
interface ParsedContent {
  type: "section" | "table" | "infobox" | "taxonIdentifier";
  title?: string; // Title for sections
  html: string; // The raw HTML content of the element
}

// ---------- PARSING FUNCTION ----------
/**
 * Parses the HTML content from the Wikipedia API response.
 * @param htmlContent The raw HTML string from the API.
 * @returns An array of ParsedContent objects.
 */
const parseWikipediaContent = (htmlContent: string): ParsedContent[] => {
  if (typeof window === "undefined") {
    return [];
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(htmlContent, "text/html");
  const contentRoot = doc.querySelector(".mw-parser-output");

  if (!contentRoot) {
    return [];
  }

  // Clone so we don't mutate the original DOM
  const cleanRoot = contentRoot.cloneNode(true) as HTMLElement;

  // --- CLEANUP PHASE ---
  // Remove edit links
  cleanRoot.querySelectorAll(".mw-editsection").forEach((el) => el.remove());

  // Remove taxobox-edit-taxonomy to keep the content clean
  cleanRoot
    .querySelectorAll(".taxobox-edit-taxonomy")
    .forEach((el) => el.remove());

  // Remove stub message blocks
  cleanRoot.querySelectorAll(".stub").forEach((el) => el.remove());

  // Remove category links section
  const catlinks = cleanRoot.querySelector("#catlinks");
  if (catlinks) catlinks.remove();

  // Optional: Remove metadata, navboxes, or anything marked as 'noprint'
  cleanRoot
    .querySelectorAll(".metadata, .noprint")
    .forEach((el) => el.remove());
  // ----------------------------------

  const parsedData: ParsedContent[] = [];
  let currentSectionHtml = "";

  cleanRoot.childNodes.forEach((node) => {
    const element = node as HTMLElement;
    if (element.nodeType !== Node.ELEMENT_NODE) return;
    // Section headings
    if (element.tagName === "DIV" && element.classList.contains("mw-heading")) {
      const h2 = element.querySelector("h2");
      if (h2) {
        if (parsedData.length > 0 && currentSectionHtml) {
          parsedData[parsedData.length - 1].html += currentSectionHtml;
        }
        currentSectionHtml = "";
        parsedData.push({
          type: "section",
          title: h2.textContent?.trim() || "Untitled",
          html: "",
        });
      }
    }
    // Tables (infobox vs regular)
    else if (element.tagName === "TABLE") {
      const isInfobox = element.classList.contains("infobox");
      parsedData.push({
        type: isInfobox ? "infobox" : "table",
        html: element.outerHTML,
      });
    }
    // Parse navbox taxon identifier
    else if (element.classList.contains("navbox")) {
      const taxonIdentifier = parseTaxonIdentifier(element.outerHTML);
      if (taxonIdentifier) {
        parsedData.push(taxonIdentifier);
      }
    }
    // All other HTML
    else if (element.outerHTML) {
      if (parsedData.length > 0) {
        parsedData[parsedData.length - 1].html += element.outerHTML;
      } else {
        currentSectionHtml += element.outerHTML;
      }
    }
  });

  return parsedData;
};

/**
 * Parses the taxon identifier table from the HTML.
 * Wikipedia renders it as a navbox. We will extract the relevant information from it.
 * Merge row table as a single span separated by middle dot for easier viewing.
 * @param html The raw HTML string containing the taxon identifier table.
 * @returns A ParsedContent object representing the table, or null if not found.
 */ function parseTaxonIdentifier(html: string): ParsedContent | null {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  const table = doc.querySelector(".navbox");
  if (!table) return null;

  // Confirm this is the "Taxon identifiers" navbox
  const headerEls = Array.from(
    table.querySelectorAll(".navbox-title, caption, th")
  );
  const isTaxonIdentifier = headerEls.some((el) =>
    /taxon identifiers?/i.test(el.textContent || "")
  );
  if (!isTaxonIdentifier) return null;

  const rows = Array.from(table.querySelectorAll("tr"));
  const parts: string[] = [];
  const seen = new Set<string>();

  rows.forEach((row) => {
    const cells = Array.from(row.children).filter((el) => el.matches("td, th"));
    if (cells.length < 2) return;

    const second = cells[1] as HTMLElement;

    Array.from(second.childNodes).forEach((node) => {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as HTMLElement;
        if (el.tagName === "A") {
          // Keep link + any trailing ID text
          let htmlPart = el.outerHTML;
          const nextText = el.nextSibling;
          if (
            nextText &&
            nextText.nodeType === Node.TEXT_NODE &&
            nextText.textContent?.trim()
          ) {
            htmlPart += " " + nextText.textContent.trim();
          }
          if (!seen.has(htmlPart)) {
            seen.add(htmlPart);
            parts.push(`<span>${htmlPart}</span>`);
          }
        } else if (!seen.has(el.outerHTML)) {
          seen.add(el.outerHTML);
          parts.push(`<span>${el.outerHTML}</span>`);
        }
      } else if (node.nodeType === Node.TEXT_NODE) {
        const txt = node.textContent?.trim();
        if (txt && !seen.has(txt)) {
          seen.add(txt);
          parts.push(`<span>${txt}</span>`);
        }
      }
    });
  });

  if (!parts.length) return null;

  return {
    type: "taxonIdentifier",
    html: parts.join("<p>"),
  };
}

function cleanWikipediaError(error: string | null): string {
  // If error contain page doesn't exist or not found
  // We return a more friendly error text. Else we show the user the error
  if (error?.includes("not found") || error?.includes("doesn't exist")) {
    return "No Wikipedia page exists for this species";
  }
  return "Failed to load Wikipedia content: " + (error || "Unknown error");
}

// Export interface as well
export { cleanWikipediaError, parseWikipediaContent };
export type { ParsedContent };
