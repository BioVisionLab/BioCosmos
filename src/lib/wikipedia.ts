// ---------- INTERFACES ----------
// Defines the structure for a piece of parsed content.
interface ParsedContent {
  type: "section" | "infobox" | "taxonIdentifier";
  /**
   * Section heading, or the taxobox's name. The lead, which comes before the
   * first heading, has none.
   */
  title?: string;
  html: string; // The cleaned HTML content of the element
}

const WIKIPEDIA_ORIGIN = "https://en.wikipedia.org";

// Back-matter sections that only make sense on Wikipedia itself: their
// citations are stripped and their links point at other wiki pages.
const DROPPED_SECTIONS = new Set([
  "see also",
  "notes",
  "footnotes",
  "references",
  "citations",
  "sources",
  "bibliography",
  "cited literature",
  "literature cited",
  "further reading",
  "external links",
]);

// Wikipedia chrome with no meaning outside the wiki: edit links, template
// styles, maintenance banners, hatnotes, citation markers and navboxes.
const REMOVED_SELECTORS = [
  "style",
  "link",
  "meta",
  ".mw-editsection",
  ".mw-empty-elt",
  ".shortdescription",
  ".taxobox-edit-taxonomy",
  ".hatnote",
  ".stub",
  ".ambox",
  ".ombox",
  ".side-box",
  ".sistersitebox",
  ".navbox-styles",
  ".authority-control",
  ".reflist",
  ".mw-references-wrap",
  "#toc",
  ".toc",
  "#catlinks",
  "sup.reference",
  ".metadata",
  ".noprint",
].join(", ");

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

  // The taxon identifiers navbox is the one navbox worth keeping. Take it out
  // before cleanup, which removes navboxes and the section it sits in.
  const taxonIdentifier = Array.from(cleanRoot.querySelectorAll(".navbox"))
    .map((el) => parseTaxonIdentifier(el as HTMLElement))
    .find((item) => item !== null);

  cleanRoot.querySelectorAll(".navbox").forEach((el) => el.remove());
  cleanRoot.querySelectorAll(REMOVED_SELECTORS).forEach((el) => el.remove());
  normalizeElements(cleanRoot);

  const parsedData: ParsedContent[] = [];
  let lead: ParsedContent | null = null;
  // The section later siblings belong to; null while inside a dropped one.
  let current: ParsedContent | null = null;
  let seenHeading = false;

  Array.from(cleanRoot.children).forEach((node) => {
    const element = node as HTMLElement;
    // Section headings
    if (element.classList.contains("mw-heading2")) {
      seenHeading = true;
      const title = element.querySelector("h2")?.textContent?.trim() || "";
      if (DROPPED_SECTIONS.has(title.toLowerCase())) {
        current = null;
        return;
      }
      current = { type: "section", title: title || "Untitled", html: "" };
      parsedData.push(current);
    }
    // The taxobox
    else if (element.tagName === "TABLE" && element.classList.contains("infobox")) {
      // The first row names the taxon; it becomes the card title instead.
      const titleRow = element.querySelector("tr");
      const title = titleRow?.querySelector("th")?.textContent?.trim();
      if (title && titleRow?.children.length === 1) titleRow.remove();
      alignRankColons(element);
      parsedData.push({ type: "infobox", title, html: element.outerHTML });
    }
    // Wide tables scroll inside their card instead of stretching it.
    else if (element.tagName === "TABLE") {
      appendTo(`<div class="wiki-table-scroll">${element.outerHTML}</div>`);
    }
    // Everything else belongs to the section it follows.
    else {
      appendTo(element.outerHTML);
    }
  });

  function appendTo(html: string) {
    if (current) {
      current.html += html;
    } else if (!seenHeading) {
      // Content before the first heading is the article's lead.
      if (!lead) {
        lead = { type: "section", html: "" };
        parsedData.unshift(lead);
      }
      lead.html += html;
    }
  }

  const sections = parsedData.filter(
    (item) => item.type !== "section" || item.html.trim() !== "",
  );
  if (taxonIdentifier) sections.push(taxonIdentifier);
  return sections;
};

/**
 * Makes the wiki HTML render with the app's styles: drops inline styles and
 * fixed widths, points links and images at absolute URLs, and opens links in
 * a new tab since they all lead off the site.
 */
function normalizeElements(root: HTMLElement) {
  root.querySelectorAll("[style], [bgcolor], table[width]").forEach((el) => {
    el.removeAttribute("style");
    el.removeAttribute("bgcolor");
    if (el.tagName === "TABLE") el.removeAttribute("width");
  });

  root.querySelectorAll("a[href]").forEach((el) => {
    const href = el.getAttribute("href") || "";
    if (href.startsWith("#")) {
      // In-page anchors point at stripped references; keep the text only.
      el.replaceWith(...Array.from(el.childNodes));
      return;
    }
    el.setAttribute("href", absoluteUrl(href));
    el.setAttribute("target", "_blank");
    el.setAttribute("rel", "noopener noreferrer");
  });

  root.querySelectorAll("img").forEach((el) => {
    const src = el.getAttribute("src");
    if (src) el.setAttribute("src", absoluteUrl(src));
    const srcset = el.getAttribute("srcset");
    if (srcset) {
      el.setAttribute(
        "srcset",
        srcset
          .split(",")
          .map((entry) => absoluteUrl(entry.trim()))
          .join(", "),
      );
    }
  });
}

/**
 * Gives the colon in each "Kingdom: Animalia" row its own column, as the
 * Taxonomy tab's fact tables do, so every colon and value lines up.
 */
function alignRankColons(infobox: HTMLElement) {
  let split = false;
  infobox.querySelectorAll("tr").forEach((row) => {
    const cells = Array.from(row.children);
    if (cells.length !== 2 || cells[0].tagName !== "TD") return;
    const label = cells[0] as HTMLElement;
    const walker = label.ownerDocument.createTreeWalker(label, NodeFilter.SHOW_TEXT);
    let last: Text | null = null;
    while (walker.nextNode()) {
      const text = walker.currentNode as Text;
      if (text.data.trim()) last = text;
    }
    if (!last || !last.data.trimEnd().endsWith(":")) return;
    last.data = last.data.trimEnd().slice(0, -1);
    const colon = label.ownerDocument.createElement("td");
    colon.className = "wiki-rank-colon";
    colon.textContent = ":";
    label.after(colon);
    split = true;
  });
  // Full-width rows (images, statuses, synonyms) now span three columns.
  if (split) {
    infobox.querySelectorAll('[colspan="2"]').forEach((cell) => {
      cell.setAttribute("colspan", "3");
    });
  }
}

function absoluteUrl(url: string): string {
  if (url.startsWith("//")) return `https:${url}`;
  if (url.startsWith("/")) return `${WIKIPEDIA_ORIGIN}${url}`;
  return url;
}

/**
 * Parses the taxon identifier table from the navbox.
 * Wikipedia renders it as a navbox. We will extract the relevant information from it.
 * Each database becomes one list item: its name, then its IDs.
 * @param table The navbox element.
 * @returns A ParsedContent object representing the table, or null if not found.
 */
function parseTaxonIdentifier(table: HTMLElement): ParsedContent | null {
  // Confirm this is the "Taxon identifiers" navbox
  const headerEls = Array.from(
    table.querySelectorAll(".navbox-title, caption, th"),
  );
  const isTaxonIdentifier = headerEls.some((el) =>
    /taxon identifiers?/i.test(el.textContent || ""),
  );
  if (!isTaxonIdentifier) return null;

  const clone = table.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(REMOVED_SELECTORS).forEach((el) => el.remove());
  normalizeElements(clone);

  // One entry per database, e.g. "BOLD: 16902". The navbox can repeat a
  // database across rows for synonyms, so dedupe on the visible text.
  const seen = new Set<string>();
  const rows: string[] = [];
  clone.querySelectorAll("td li").forEach((item) => {
    const text = item.textContent?.trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    rows.push(`<li>${item.innerHTML.trim()}</li>`);
  });

  if (!rows.length) return null;

  return {
    type: "taxonIdentifier",
    html: `<ul class="wiki-identifiers">${rows.join("")}</ul>`,
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
