"use client";

import Info from "@/components/Info";
import { TextLoading } from "@/components/Loadings";
import {
  ParsedContent,
  parseWikipediaContent,
  cleanWikipediaError,
} from "@/lib/wikipedia";
import React, { useEffect, useState } from "react";

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

type PageState =
  | { speciesName: string; status: "loaded"; content: ParsedContent[] }
  | { speciesName: string; status: "failed"; error: string };

function WikipediaPage({ speciesName }: { speciesName: string }) {
  // Keyed by the species it was fetched for, so a change of species reads as
  // loading without resetting state synchronously inside the effect.
  const [state, setState] = useState<PageState | null>(null);

  useEffect(() => {
    // The tab can mount before the species data arrives; wait for a name.
    const title = speciesName.trim();
    if (!title) return;
    let isMounted = true;
    fetchWikipediaPage(title)
      .then(({ html }) => {
        if (!isMounted) return;
        const content = parseWikipediaContent(html);
        setState({ speciesName, status: "loaded", content });
      })
      .catch((err: Error) => {
        if (isMounted) {
          setState({ speciesName, status: "failed", error: err.message });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [speciesName]);

  if (state?.speciesName !== speciesName) {
    return <TextLoading msg="Loading Wikipedia article" />;
  }

  if (state.status === "failed" || state.content.length === 0) {
    return (
      <Empty
        text={cleanWikipediaError(
          state.status === "failed" ? state.error : "Page content not found",
        )}
      />
    );
  }

  const infobox = state.content.find((item) => item.type === "infobox");
  const sections = state.content.filter((item) => item.type === "section");
  const taxonIdentifier = state.content.find(
    (item) => item.type === "taxonIdentifier",
  );

  return (
    <div>
      <WikipediaAttribution speciesName={speciesName} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-5 min-w-0">
          {sections.map((item, index) => (
            <Card key={index} title={item.title ?? "Summary"}>
              <WikiHtml html={item.html} />
            </Card>
          ))}
        </div>

        <aside className="lg:col-span-1 space-y-5 min-w-0">
          {infobox ? (
            <Card title={infobox.title ?? "At a glance"}>
              <WikiHtml html={infobox.html} />
            </Card>
          ) : null}
          {taxonIdentifier ? (
            <Card title="Taxon identifiers">
              <WikiHtml html={taxonIdentifier.html} />
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

/** Cleaned Wikipedia HTML, styled by the `.wiki-content` rules in globals.css. */
function WikiHtml({ html }: { html: string }) {
  return (
    <div className="wiki-content" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

// The same card the Taxonomy tab uses, so the two tabs read as a set.
function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-linear-to-r from-white/50 to-white/30 dark:from-pacific-blue-900/30 dark:to-deep-mocha-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-linear-to-br from-pacific-blue-500/20 to-hunter-green-300/10 p-4 rounded-t-xl">
        <h2 className="text-2xl font-semibold">{title}</h2>
      </div>
      <div className="p-4 text-sm text-deep-mocha-700 dark:text-deep-mocha-300">
        {children}
      </div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-xl bg-white/40 dark:bg-deep-mocha-800/40 p-6">
      <p className="text-deep-mocha-500 dark:text-deep-mocha-400">{text}</p>
    </div>
  );
}

/**
 * Fetches and processes a Wikipedia page's HTML content.
 * @param title The title of the Wikipedia page to fetch.
 * @returns The processed HTML content of the page.
 */
const fetchWikipediaPage = async (
  title: string,
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
    // Relative links and images are made absolute when the HTML is parsed.
    return { title: pageTitle, html: pageHtml };
  } else {
    throw new Error(`Page content not found for "${title}". It may not exist.`);
  }
};

function WikipediaAttribution({ speciesName }: { speciesName: string }) {
  return (
    <div className="mb-4">
      <Info>
        <p>
          Content adapted from{" "}
          <a
            href={`https://en.wikipedia.org/wiki/${speciesName}`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-pacific-blue-700 dark:hover:text-pacific-blue-300"
          >
            English Wikipedia (<span className="italic">{speciesName}</span>)
          </a>{" "}
          and cleaned for readability; citations and reference sections are
          omitted. It may contain community-edited or unverified information.
          Verify with primary sources.
        </p>
      </Info>
    </div>
  );
}

export default WikipediaPage;
