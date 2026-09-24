import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { ITALIC_COL_RANKS } from "@/lib/colTaxonomy";
import type { TaxonNode } from "@/lib/higherTaxa";

/**
 * Above this many nodes, the rank carrying the bulk starts collapsed.
 *
 * Nymphalidae has around 470 genera under a dozen subfamilies. Rendering
 * them all is cheap, but opening on 470 rows pushes the subfamilies off the
 * screen before a reader has seen that the family has subfamilies at all.
 */
const AUTO_EXPAND_LIMIT = 120;

const ROW =
  "inline-flex flex-wrap items-baseline gap-x-2 gap-y-0.5 min-w-0 py-0.5 pr-2 rounded-lg";

const SUMMARY =
  "cursor-pointer marker:content-none [&::-webkit-details-marker]:hidden " +
  "hover:bg-hunter-green-500/10 dark:hover:bg-hunter-green-500/15 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hunter-green-500";

// Connector elbows as pseudo-elements. A pseudo-element is never in the
// accessibility tree, so unlike a decorative <span> there is no aria-hidden
// here to forget.
const LIST =
  "list-none m-0 pl-4 ml-2 border-l border-deep-mocha-300/60 dark:border-deep-mocha-600/60";
const ITEM =
  "relative pl-4 py-px before:absolute before:left-0 before:top-[0.85em] " +
  "before:h-px before:w-3 before:bg-deep-mocha-300/60 dark:before:bg-deep-mocha-600/60";

const RANK_TAG =
  "shrink-0 text-[0.625rem] uppercase tracking-wider font-semibold " +
  "text-hunter-green-700/70 dark:text-hunter-green-400/70";
const BADGE =
  "shrink-0 rounded-full px-1.5 text-[0.6875rem] font-medium tabular-nums " +
  "bg-pacific-blue-500/15 text-pacific-blue-800 dark:text-pacific-blue-200";
const MUTED =
  "shrink-0 text-[0.6875rem] tabular-nums text-deep-mocha-500 dark:text-deep-mocha-400";

// The taxon the page is about, when it appears in its own tree. The same pill
// the species rung wears in the classification ladder.
const HIGHLIGHT =
  "rounded-md px-2 py-0.5 box-decoration-clone bg-gradient-to-r " +
  "from-hunter-green-500/20 to-pacific-blue-500/20 font-semibold " +
  "text-deep-mocha-900 dark:text-deep-mocha-50";

type BottomRank = "family" | "genus" | "species";

/**
 * The key to the greyed-out rows, set under each tree. `taxa` is the plural
 * of the tree's bottom rank: "families", "genera" or "species".
 */
export function UnrecordedTaxaNote({ taxa }: { taxa: string }) {
  return (
    <p className="mt-3 text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
      Linked {taxa} have records in the collection. {taxa[0].toUpperCase()}
      {taxa.slice(1)} in grey are in the Catalogue of Life classification but
      have no images here yet.
    </p>
  );
}

export interface TaxonomyTreeProps {
  nodes: TaxonNode[];
  /** The rank the tree stops at, which decides which nodes are links. */
  bottomRank: BottomRank;
  /** Nodes of this rank are the page's own taxon, and are highlighted. */
  highlightRank?: string;
  /** Every node in the tree, used to pick the default expansion. */
  nodeCount: number;
  /** A stable id so the controls island can find this subtree. */
  id: string;
}

/**
 * A classification rendered as nested lists of native disclosures.
 *
 * `<details>` rather than React state, which makes this a server component:
 * expanding, collapsing and keyboard operation all work with no JavaScript
 * and nothing hydrated, which matters when a family has several hundred
 * genera. It also means there are no element ids to collide, no
 * `aria-expanded` to keep in sync, and no `aria-controls` to get wrong — the
 * browser derives all of it from `open`.
 *
 * The constraint that buys: `open` is uncontrolled DOM state that React
 * writes once and never reconciles. Nothing in this tree's ancestry may hold
 * React state that triggers a re-render, or every node would snap back to the
 * state the server chose. Nothing does today.
 *
 * On every page every node that links somewhere is a leaf and every node with
 * children links nowhere, so a link never sits inside a `<summary>` and
 * clicking one cannot also toggle a disclosure.
 */
export default function TaxonomyTree({
  nodes,
  bottomRank,
  highlightRank,
  nodeCount,
  id,
}: TaxonomyTreeProps) {
  const eager = nodeCount <= AUTO_EXPAND_LIMIT;
  return (
    <div id={id} className="text-sm overflow-x-auto">
      <ul className="list-none m-0 p-0">
        {nodes.map((node) => (
          <TreeNode
            key={`${node.rank}:${node.key}`}
            node={node}
            bottomRank={bottomRank}
            highlightRank={highlightRank}
            eager={eager}
          />
        ))}
      </ul>
    </div>
  );
}

function TreeNode({
  node,
  bottomRank,
  highlightRank,
  eager,
}: {
  node: TaxonNode;
  bottomRank: BottomRank;
  highlightRank?: string;
  eager: boolean;
}) {
  const hasChildren = node.children.length > 0;

  // The grouping ranks are few — a family has a dozen subfamilies, not
  // hundreds — and seeing them is the point of the page, so they stay open.
  // Only the level holding the bulk collapses, and only when there is bulk.
  const childrenAreTerminal = node.children[0]?.rank === bottomRank;
  // The order tree is the exception: most of its forty-odd superfamilies are
  // moths the collection holds nothing of, so the few with images open and
  // the rest stay folded.
  const open =
    eager ||
    !childrenAreTerminal ||
    (bottomRank === "family" && node.imageCount > 0);

  return (
    <li className={ITEM} data-taxon-name={node.name.toLowerCase()}>
      {hasChildren ? (
        <details
          open={open}
          // Recorded so the filter can put the tree back exactly as the
          // server drew it, rather than guessing which levels were open.
          data-default-open={open ? "true" : "false"}
          className="group/node"
        >
          <summary className={`${ROW} ${SUMMARY}`}>
            <ChevronRight
              aria-hidden="true"
              className="h-3.5 w-3.5 shrink-0 self-center text-hunter-green-600 dark:text-hunter-green-400 transition-transform duration-150 group-open/node:rotate-90"
            />
            <NodeLabel
              node={node}
              bottomRank={bottomRank}
              highlightRank={highlightRank}
            />
          </summary>
          <ul className={LIST}>
            {node.children.map((child) => (
              <TreeNode
                key={`${child.rank}:${child.key}`}
                node={child}
                bottomRank={bottomRank}
                highlightRank={highlightRank}
                eager={eager}
              />
            ))}
          </ul>
        </details>
      ) : (
        <span className={`${ROW} pl-5`}>
          <NodeLabel
            node={node}
            bottomRank={bottomRank}
            highlightRank={highlightRank}
          />
        </span>
      )}
    </li>
  );
}

function NodeLabel({
  node,
  bottomRank,
  highlightRank,
}: {
  node: TaxonNode;
  bottomRank: BottomRank;
  highlightRank?: string;
}) {
  const italic = ITALIC_COL_RANKS.has(node.rank) ? "italic" : "";
  // Only the terminal rank has a page of its own. The ranks in between are
  // plain text because there is nowhere to send a reader who clicks one.
  const href = node.rank === bottomRank ? node.href : null;
  // A terminal node without a page: a family, genus or species Catalogue of
  // Life lists but the collection holds nothing of. Shown, because it is part
  // of the classification, but set back so it does not read as a dead link.
  const empty = node.rank === bottomRank && !href;
  const highlighted = !!highlightRank && node.rank === highlightRank;
  const nameTone = empty
    ? "text-deep-mocha-500 dark:text-deep-mocha-400"
    : "text-deep-mocha-800 dark:text-deep-mocha-100";

  return (
    <>
      <span className={RANK_TAG}>{node.rank}</span>
      {href ? (
        // prefetch={false}: a family renders several hundred of these, and the
        // router would otherwise fire a prefetch for every one that scrolls
        // into view.
        <Link
          href={href}
          prefetch={false}
          className={`${italic} font-medium text-pacific-blue-700 dark:text-pacific-blue-300 hover:underline`}
        >
          {node.name}
        </Link>
      ) : highlighted ? (
        <span className={`${italic} ${HIGHLIGHT}`}>{node.name}</span>
      ) : (
        <span className={`${italic} font-medium ${nameTone}`}>{node.name}</span>
      )}
      {node.authorship ? (
        <span className="text-deep-mocha-500 dark:text-deep-mocha-400 text-xs font-normal">
          {node.authorship}
        </span>
      ) : null}
      {/* Two species can carry the same accepted name when one of them was
          recorded under a name Catalogue of Life has since synonymised. This
          is what tells them apart, so it is not decoration. */}
      {node.recordedName ? (
        <span className="text-deep-mocha-500 dark:text-deep-mocha-400 text-xs italic">
          recorded as {node.recordedName}
        </span>
      ) : null}
      {node.familyCount ? (
        <span className={BADGE}>
          {node.familyCount.toLocaleString()}
          <span className="sr-only">
            {node.familyCount === 1 ? " family" : " families"}
          </span>
          <span aria-hidden="true"> fam</span>
        </span>
      ) : null}
      {/* Suppressed on leaves: "0 genera" is the one thing a reader of a leaf
          already knows. */}
      {node.genusCount ? (
        <span className={BADGE}>
          {node.genusCount.toLocaleString()}
          <span className="sr-only">
            {node.genusCount === 1 ? " genus" : " genera"}
          </span>
          <span aria-hidden="true"> gen</span>
        </span>
      ) : null}
      {node.speciesCount > 1 ? (
        <span className={BADGE}>
          {node.speciesCount.toLocaleString()}
          <span className="sr-only"> species</span>
          <span aria-hidden="true"> spp</span>
        </span>
      ) : null}
      {node.imageCount > 0 ? (
        <span className={MUTED}>
          {node.imageCount.toLocaleString()}
          <span className="sr-only">
            {node.imageCount === 1 ? " image" : " images"}
          </span>
          <span aria-hidden="true"> img</span>
        </span>
      ) : null}
    </>
  );
}
