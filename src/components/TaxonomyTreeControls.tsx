"use client";

import { Search, X } from "lucide-react";
import { useId, useRef } from "react";

/**
 * Expand, collapse and filter a `TaxonomyTree`.
 *
 * Everything here works on the DOM rather than on React state, and that is
 * the point: the tree is a server component holding several hundred nodes,
 * and lifting `open` into React to serve two buttons and a text field would
 * mean hydrating all of them. `open` is uncontrolled, so writing it here is
 * not fighting a later render — there is no later render.
 *
 * Without JavaScript this bar does nothing, which is acceptable: it only
 * accelerates what `<summary>` already does one node at a time.
 */
export default function TaxonomyTreeControls({
  treeId,
  label = "Filter by name",
}: {
  treeId: string;
  label?: string;
}) {
  const inputId = useId();
  // The timer, not a value: nothing here needs a re-render, and a `useState`
  // would give this component one for every keystroke.
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);

  const tree = () => document.getElementById(treeId);

  const setAll = (open: boolean) => {
    tree()
      ?.querySelectorAll<HTMLDetailsElement>("details")
      .forEach((node) => {
        node.open = open;
      });
  };

  const applyFilter = (rawQuery: string) => {
    const root = tree();
    if (!root) return;
    const query = rawQuery.trim().toLowerCase();
    const items = root.querySelectorAll<HTMLLIElement>("li[data-taxon-name]");

    if (!query) {
      // Put the tree back exactly as the server drew it, rather than leaving
      // it open or guessing: a cleared field should look like an untouched
      // page. Each disclosure carries the state it was rendered with.
      items.forEach((item) => {
        item.hidden = false;
      });
      root
        .querySelectorAll<HTMLDetailsElement>("details")
        .forEach((node) => {
          node.open = node.dataset.defaultOpen === "true";
        });
      return;
    }

    // Hide everything, then walk each match back up to the root revealing and
    // opening its ancestors, so a matching genus stays visible under the
    // subfamily it belongs to instead of being lifted out of the hierarchy.
    items.forEach((item) => {
      item.hidden = true;
    });
    items.forEach((item) => {
      if (!item.dataset.taxonName?.includes(query)) return;
      let node: HTMLElement | null = item;
      while (node && node !== root) {
        if (node instanceof HTMLLIElement) {
          node.hidden = false;
          const disclosure = node.querySelector<HTMLDetailsElement>(":scope > details");
          if (disclosure) disclosure.open = true;
        }
        node = node.parentElement;
      }
      // Descendants of a match come with it: a subfamily that matches shows
      // the genera under it.
      item.querySelectorAll<HTMLLIElement>("li[data-taxon-name]").forEach((child) => {
        child.hidden = false;
      });
    });
  };

  const onInput = (value: string) => {
    if (pending.current) clearTimeout(pending.current);
    pending.current = setTimeout(() => applyFilter(value), 120);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-deep-mocha-500"
        />
        <input
          id={inputId}
          type="search"
          placeholder={label}
          onChange={(event) => onInput(event.target.value)}
          className="w-48 rounded-full border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 py-1 pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-hunter-green-500"
        />
      </div>
      <button type="button" onClick={() => setAll(true)} className={GHOST}>
        Expand all
      </button>
      <button type="button" onClick={() => setAll(false)} className={GHOST}>
        <X aria-hidden="true" className="h-3 w-3" />
        Collapse all
      </button>
    </div>
  );
}

const GHOST =
  "inline-flex items-center gap-1 rounded-full border border-deep-mocha-300 " +
  "dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 px-3 py-1 " +
  "text-xs font-medium hover:bg-hunter-green-500/10 focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-hunter-green-500";
