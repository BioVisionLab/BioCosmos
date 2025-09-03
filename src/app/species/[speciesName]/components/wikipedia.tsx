"use client";

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
    <div className="space-y-2 text-xs text-gray-600">
      <div className="rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-[11px] leading-snug text-gray-700">
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
            className="underline"
          >
            English Wikipedia (<span className="italic">{speciesName}</span>)
          </a>
        </p>
      </div>
    </div>
  );
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
      <div className="rounded-2xl p-6">
        {isLoading && (
          <div className="text-center p-10 rounded-xl">
            <p className="text-xl text-gray-600">Loading content...</p>
          </div>
        )}

        {error && (
          <div className="text-center text-gray-600 p-10 rounded-xl">
            <p>{cleanWikipediaError(error)}</p>
          </div>
        )}

        {!isLoading && !error && parsedContent.length > 0 && (
          <>
            <div
              className={`font-sans text-gray-900 rounded-2xl bg-gradient-to-tr from-white to-green-50 p-6 backdrop-blur-lg shadow border border-gray-300 dark:border-gray-600`}
            >
              <WikipediaAttribution speciesName={speciesName} />
              <div className="rounded-xl overflow-hidden">
                <div className="p-4 md:p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-2 space-y-8">
                    {mainContent.map((item, index) => (
                      <div key={index}>
                        {item.type === "section" && (
                          <section>
                            <h2 className="text-2xl font-semibold border-b pb-2 mb-4">
                              {item.title}
                            </h2>
                            <div
                              className="dynamic-content"
                              dangerouslySetInnerHTML={{ __html: item.html }}
                            />
                          </section>
                        )}
                        {item.type === "table" && (
                          // Full-bleed (viewport-wide) table container
                          <div className="w-screen relative left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] overflow-x-auto border bg-white">
                            <div
                              className="border border-gray-200 inline-block min-w-full"
                              dangerouslySetInnerHTML={{ __html: item.html }}
                            />
                          </div>
                        )}
                        {item.type === "taxonIdentifier" && (
                          <div className="rounded-2xl">
                            <h3 className="text-lg font-semibold mb-2">
                              Taxon Identifier
                            </h3>
                            <div
                              className="dynamic-content pl-2"
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
                          className="border bg-gradient-to-r from-emerald-100  to-teal-100 rounded-xl overflow-hidden w-[22em] max-w-full p-4 md:p-8"
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

export default WikipediaPage;
