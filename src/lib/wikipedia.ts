// ---------- INTERFACES ----------
// Defines the structure for a piece of parsed content.
interface ParsedContent {
  type: "section" | "table" | "infobox";
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

  const cleanRoot = contentRoot.cloneNode(true) as HTMLElement;
  cleanRoot.querySelectorAll(".mw-editsection").forEach((el) => el.remove());

  const parsedData: ParsedContent[] = [];
  let currentSectionHtml = "";
  let introContentCollected = false;

  cleanRoot.childNodes.forEach((node) => {
    const element = node as HTMLElement;
    if (element.nodeType !== Node.ELEMENT_NODE) return;

    if (element.tagName === "DIV" && element.classList.contains("mw-heading")) {
      const h2 = element.querySelector("h2");
      if (h2) {
        if (!introContentCollected && currentSectionHtml.trim()) {
          parsedData.push({
            type: "section",
            title: "Introduction",
            html: currentSectionHtml,
          });
          introContentCollected = true;
        } else if (parsedData.length > 0) {
          parsedData[parsedData.length - 1].html += currentSectionHtml;
        }
        currentSectionHtml = "";
        parsedData.push({
          type: "section",
          title: h2.textContent?.trim() || "Untitled",
          html: "",
        });
      }
    } else if (element.tagName === "TABLE") {
      const isInfobox = element.classList.contains("infobox");
      parsedData.push({
        type: isInfobox ? "infobox" : "table",
        html: element.outerHTML,
      });
    } else if (element.outerHTML) {
      if (parsedData.length > 0) {
        parsedData[parsedData.length - 1].html += element.outerHTML;
      } else {
        currentSectionHtml += element.outerHTML;
      }
    }
  });

  if (!introContentCollected && currentSectionHtml.trim()) {
    parsedData.push({
      type: "section",
      title: "Introduction",
      html: currentSectionHtml,
    });
  }

  return parsedData;
};

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
