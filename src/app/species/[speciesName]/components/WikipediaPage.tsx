"use client";

import Info from "@/components/Info";
import { NoData } from "@/components/NoData";
import {
  ParsedContent,
  parseWikipediaContent,
  cleanWikipediaError,
} from "@/lib/wikipedia";
import React, { useState, useEffect } from "react";

// Defines the structure of the raw Wikipedia API response.
// Note: This is a simplified interface for the 'parse' action.
interface WikipediaApiParseResponse {
  parse?: {
    title: string;
    pageid: number;
    text: {
      "*": string;
    };
  };
  error?: {
    code: string;
    info: string;
  };
}

function WikipediaPage({ speciesName }: { speciesName: string }) {
  const [parsedContent, setParsedContent] = useState<ParsedContent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    if (!speciesName.trim()) {
      setError("Please enter a search term.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setParsedContent([]);

    try {
      const { html } = await fetchWikipediaPage(speciesName.trim());
      const content = parseWikipediaContent(html);
      setParsedContent(content);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch a default page on initial load
  useEffect(() => {
    handleSearch();
  }, []);

  const infobox = parsedContent.find((item) => item.type === "infobox");
  const mainContent = parsedContent.filter((item) => item.type !== "infobox");

  return (
    <>
      {/* CSS overrides scoped to the wiki-rendered HTML to normalize infobox headings and colors */}
      <style>{`
        /* Target Wikipedia infobox/table headers and captions that often carry inline beige backgrounds */
        .wiki-container .infobox th,
        .wiki-container .infobox caption,
        .wiki-container .infobox .fn,
        .wiki-container .infobox caption span {
          background: transparent !important;
          background-color: transparent !important;
          color: inherit !important;
        }
        .wiki-container .infobox {
          background: transparent !important;
          /* Use separate border model and vertical spacing between rows so each header/section breathes */
          border-collapse: separate !important;
          border-spacing: 0 0.6rem !important;
          border-color: oklch(98.5% 0.002 247.839) !important;
        }
        /* Default (light) colors */
        .wiki-container .infobox td,
        .wiki-container .infobox th,
        .wiki-container .infobox tr,
        .wiki-container .infobox caption {
          color: oklch(25% 0.02 247.839) !important;
        }
        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .wiki-container .infobox {
            border-color: oklch(40% 0.015 247.839) !important;
          }
          .wiki-container .infobox td,
          .wiki-container .infobox th,
          .wiki-container .infobox tr,
          .wiki-container .infobox caption {
            color: oklch(88% 0.008 247.839) !important;
          }
        }
          /* Override IUCN colors in dark mode */
          .wiki-container [style*="background-color"] {
            background-color: transparent !important;
          }
        }
        
        /* Default colors for table head background color */
        .wiki-container table.wikitable th {
          background-color: oklch(95% 0.01 250) !important;
          color: oklch(20% 0.05 250) !important;
        }
        /* Default colors for table head background color */
        .wiki-container table.wikitable th {
          background-color: oklch(95% 0.01 250) !important;
          color: oklch(20% 0.05 250) !important;
        }
        @media (prefers-color-scheme: dark) {
          .wiki-container table.wikitable th {
            background-color: oklch(25% 0.03 250) !important;
            color: oklch(90% 0.01 250) !important;
          }
        }  
        /* Make wiki links inherit surrounding text color and only show an underline for clarity
           (avoids bright-blue links on dark/blue backgrounds). Scoped to wiki-container. */
        .wiki-container a,
        .wiki-container a:visited {
          color: inherit !important;
          text-decoration: underline !important;
          text-decoration-color: currentColor !important;
          text-underline-offset: 2px !important;
        }
        /* Prevent images/tables inside wiki HTML from overflowing their container */
        .wiki-container img { max-width: 100%; height: auto; }
      `}</style>

      <div className="rounded-2xl p-6">
        {isLoading && (
          <div className="text-center p-10 rounded-xl">
            <p className="text-xl text-slate-600 dark:text-emerald-100">
              Loading content...
            </p>
          </div>
        )}

        {error && <NoData text={cleanWikipediaError(error)} />}

        {!isLoading && !error && parsedContent.length > 0 && (
          <>
            <div
              className={`font-sans rounded-2xl p-6 shadow-lg backdrop-blur-sm
                bg-white/80 text-slate-800 border border-slate-200
                dark:bg-gradient-to-tr dark:from-gray-900 dark:via-gray-800 dark:to-gray-700 dark:text-emerald-100 dark:border-slate-700`}
            >
              <WikipediaAttribution speciesName={speciesName} />
              <div className="rounded-xl overflow-hidden bg-transparent">
                {/* wrapper to scope wiki HTML overrides */}
                <div className="wiki-container p-4 md:p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-2 space-y-8">
                    {mainContent.map((item, index) => (
                      <div key={index}>
                        {item.type === "section" && (
                          <section>
                            <h2
                              className="text-2xl font-semibold border-b-2 pb-2 mb-4
                              text-gray-900 dark:text-gray-100 border-gray-200 dark:border-teal-700"
                            >
                              {item.title}
                            </h2>
                            <div
                              className="dynamic-content text-gray-800 dark:text-gray-100"
                              dangerouslySetInnerHTML={{ __html: item.html }}
                            />
                          </section>
                        )}
                        {item.type === "table" && (
                          // Full-bleed (viewport-wide) table container
                          <div
                            className="w-screen relative left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] overflow-x-auto border
                            border-slate-200 dark:border-slate-600 bg-slate-50/60 dark:bg-slate-800/60 text-slate-700 dark:text-emerald-100"
                          >
                            <div
                              className="inline-block min-w-full p-4"
                              dangerouslySetInnerHTML={{ __html: item.html }}
                            />
                          </div>
                        )}
                        {item.type === "taxonIdentifier" && (
                          <div className="rounded-2xl">
                            <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">
                              Taxon Identifier
                            </h3>
                            <div
                              className="dynamic-content pl-2 text-gray-800 dark:text-gray-100"
                              dangerouslySetInnerHTML={{ __html: item.html }}
                            />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <aside className="lg:col-auto">
                    {infobox && (
                      <div className="sticky top-8 mx-auto flex justify-center items-center">
                        <div
                          className="rounded-xl overflow-hidden w-[22em] max-w-full p-4 md:p-8
                          bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-500/50
                            dark:bg-gradient-to-r dark:from-teal-800 dark:to-emerald-600/50 dark:text-gray-100"
                          dangerouslySetInnerHTML={{ __html: infobox.html }}
                        />
                      </div>
                    )}
                  </aside>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

/**
 * Fetches and processes a Wikipedia page's HTML content.
 * @param title The title of the Wikipedia page to fetch.
 * @returns The processed HTML content of the page.
 */
const fetchWikipediaPage = async (
  title: string
): Promise<{ title: string; html: string }> => {
  if (!title) {
    throw new Error("Title is required");
  }
  const WIKIPEDIA_API_URL = `https://en.wikipedia.org/w/api.php`;
  const params = new URLSearchParams({
    action: "parse",
    page: title,
    format: "json",
    prop: "text",
    redirects: "true",
    origin: "*", // Required for client-side CORS requests
  });

  const response = await fetch(`${WIKIPEDIA_API_URL}?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Wikipedia API returned status: ${response.status}`);
  }
  const data: WikipediaApiParseResponse = await response.json();
  if (data.error) {
    throw new Error(`Wikipedia error: ${data.error.info}`);
  }

  const pageHtml = data.parse?.text["*"];
  const pageTitle = data.parse?.title || title;

  if (pageHtml) {
    // Replace relative URLs with absolute URLs for links and images
    const processedHtml = pageHtml
      .replace(/href="\/wiki\//g, 'href="https://en.wikipedia.org/wiki/')
      .replace(/src="\/\//g, 'src="https://');
    return { title: pageTitle, html: processedHtml };
  } else {
    throw new Error(`Page content not found for "${title}". It may not exist.`);
  }
};

function WikipediaAttribution({ speciesName }: { speciesName: string }) {
  return (
    <div className="space-y-2 text-xs">
      <Info>
        <p>
          Content adapted from English Wikipedia (en.wikipedia.org) and lightly
          cleaned for readability. It may contain community-edited or unverified
          information. Verify with primary sources.
        </p>
        <p>
          Source URL:{" "}
          <a
            href={`https://en.wikipedia.org/wiki/${speciesName}`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline "
          >
            English Wikipedia (<span className="italic">{speciesName}</span>)
          </a>
        </p>
      </Info>
    </div>
  );
}

export default WikipediaPage;
