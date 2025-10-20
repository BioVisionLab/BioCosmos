/*
Literature search via CrossRef API
*/

import {
  decodeHtmlEntities,
  toAuthorNameCase,
  toSentenceCase,
  toTitleCase,
} from "./textUtils";

const API_BASE_URL = "https://api.crossref.org/types/journal-article/works?";

export interface CrossRefResult {
  title: string;
  authors: string[];
  published_year?: number;
  journal: string;
  volume?: string;
  issue?: string;
  pages?: string;
  doi?: string;
}

async function queryCrossRef(speciesName: string): Promise<any> {
  // Use query.bibliographic for titles/citations instead of general query
  // It searches titles, authors, ISSNs, and publication years
  const params = new URLSearchParams({
    "query.bibliographic": `${speciesName} butterfly Lepidoptera`,
    rows: "20", // Increased from 15 for better coverage
    sort: "relevance", // Explicitly sort by relevance score
    order: "desc",
    filter: "from-pub-date:2000-01-01,type:journal-article,has-abstract:true",
    select:
      "DOI,title,author,published,container-title,abstract,is-referenced-by-count",
  });

  try {
    const response = await fetch(`${API_BASE_URL}${params.toString()}`);

    if (!response.ok) {
      throw new Error(
        `Failed to fetch CrossRef data for ${speciesName}: ${response.statusText}`
      );
    }

    return response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}

function parsePublishedYear(item: any): number | undefined {
  const toYear = (v: unknown): number | undefined => {
    const n = typeof v === "string" ? parseInt(v, 10) : Number(v);
    return Number.isFinite(n) ? n : undefined;
  };

  if (item?.published?.["date-parts"]?.[0]?.[0] != null) {
    const y = toYear(item.published["date-parts"][0][0]);
    if (y !== undefined) return y;
  }
  if (item?.["published-print"]?.["date-parts"]?.[0]?.[0] != null) {
    const y = toYear(item["published-print"]["date-parts"][0][0]);
    if (y !== undefined) return y;
  }
  if (item?.["published-online"]?.["date-parts"]?.[0]?.[0] != null) {
    const y = toYear(item["published-online"]["date-parts"][0][0]);
    if (y !== undefined) return y;
  }
  return undefined;
}

/* Fetches literature data from CrossRef API based on species name
We group the results by year so it is not cluttered for viewing 
*/
async function fetchCrossRefData(
  speciesName: string
): Promise<Record<string, CrossRefResult[]>> {
  const results: Record<string, CrossRefResult[]> = {};
  const data = await queryCrossRef(speciesName);
  if (!data) {
    return results;
  }

  for (const item of data.message.items) {
    // We turn all title into sentence case for consistency
    const decodedTitle = decodeHtmlEntities(
      item.title ? item.title[0] : "No title available"
    );
    const title = toSentenceCase(decodedTitle);
    const authors = item.author
      ? item.author.map((a: any) => toAuthorNameCase(`${a.given} ${a.family}`))
      : ["No authors available"];
    const published_year = parsePublishedYear(item);
    const journal = decodeHtmlEntities(
      item["container-title"]
        ? item["container-title"][0]
        : "No journal available"
    );
    const volume = item.volume;
    const issue = item.issue;
    const pages = item.pages;
    const doi = item.DOI;

    if (published_year) {
      if (!results[published_year]) {
        results[published_year] = [];
      }
      results[published_year].push({
        title,
        authors,
        published_year,
        journal,
        volume,
        issue,
        pages,
        doi,
      });
    } else {
      if (!results["Unknown Year"]) {
        results["Unknown Year"] = [];
      }
      results["Unknown Year"].push({
        title,
        authors,
        journal,
        volume,
        issue,
        pages,
        doi,
      });
    }
  }
  return results;
}

export { fetchCrossRefData };
