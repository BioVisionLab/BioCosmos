"use client";

import {
  CodeDescriptions,
  CodeKind,
  CodeTone,
  TaxonUpdate,
  describeCode,
  fetchCodeDescriptions,
  humanizeCode,
  statusLabel,
  statusShortLabel,
  toneClasses,
  toneForStatus,
} from "@/lib/colTaxonomy";
import { Lightbulb } from "lucide-react";
import React, { useEffect, useId, useRef, useState } from "react";

/**
 * Descriptions are fetched once per page load and shared by every hint.
 *
 * A search results page renders one of these per row, so each holding its own
 * request would be wasteful; `fetchCodeDescriptions` dedupes them into a
 * single module-level promise.
 */
function useCodeDescriptions(): CodeDescriptions | null {
  const [descriptions, setDescriptions] = useState<CodeDescriptions | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    void fetchCodeDescriptions().then((loaded) => {
      if (active) setDescriptions(loaded);
    });
    return () => {
      active = false;
    };
  }, []);

  return descriptions;
}

export interface CodeHintProps {
  /** A raw code, e.g. "AMBIGUOUS" or "GENUS_SPELLING_EPITHET". */
  code: string | null | undefined;
  kind: CodeKind;
  /** Visible text; defaults to a humanized form of the code. */
  label?: string;
  /** Prose to show instead of the fetched description. */
  description?: string | null;
  tone?: CodeTone;
  /** "badge" is a pill; "text" is an underlined inline label. */
  variant?: "badge" | "text";
  className?: string;
}

/**
 * A code that explains itself when clicked.
 *
 * An inline disclosure rather than a popover: the search results table lives
 * inside `overflow-x-auto`, which also clips vertically, so an absolutely
 * positioned panel inside a cell would be cut off and would need a portal to
 * escape. This also works on touch, where hover does not.
 */
export function CodeHint({
  code,
  kind,
  label,
  description,
  tone = "neutral",
  variant = "badge",
  className = "",
}: CodeHintProps) {
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const descriptions = useCodeDescriptions();

  if (!code) return null;

  const visibleLabel = label ?? humanizeCode(code);
  const text = description ?? describeCode(code, kind, descriptions);

  const labelClasses =
    variant === "badge"
      ? `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses(tone)}`
      : "inline-flex items-center gap-1 text-xs text-deep-mocha-600 dark:text-deep-mocha-400";

  // Without prose there is nothing to reveal, so render a plain label rather
  // than a control that does nothing when clicked.
  if (!text) {
    return (
      <span className={`${labelClasses} ${className}`}>{visibleLabel}</span>
    );
  }

  return (
    <span className={`inline-flex flex-col items-start gap-1 min-w-0 ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-describedby={open ? panelId : undefined}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            // Stop here so a hint inside the specimen modal closes itself
            // without also closing the modal, which listens on the window.
            event.stopPropagation();
            setOpen(false);
            triggerRef.current?.focus();
          }
        }}
        className={`${labelClasses} cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hunter-green-500 ${
          variant === "text" ? "underline decoration-dotted underline-offset-2" : ""
        }`}
      >
        <span className="truncate">{visibleLabel}</span>
        <Lightbulb className="h-3 w-3 shrink-0 opacity-70" aria-hidden="true" />
        <span className="sr-only">
          {open ? " — hide explanation" : " — show explanation"}
        </span>
      </button>
      <span
        id={panelId}
        role="note"
        aria-hidden={!open}
        // The panel stays mounted so aria-controls always resolves. Toggling
        // the class rather than the `hidden` attribute, because a `flex` class
        // on the same element would override `[hidden] { display: none }`.
        className={
          open
            ? "flex items-start gap-1.5 border-l-8 border border-deep-mocha-600/40 bg-deep-mocha-100/10 dark:bg-deep-mocha-800/20 rounded-lg p-2 max-w-xs text-xs font-normal normal-case leading-normal text-deep-mocha-600 dark:text-deep-mocha-400"
            : "hidden"
        }
      >
        <span>{text}</span>
      </span>
    </span>
  );
}

export interface TaxonStatusBadgeProps {
  update: Pick<TaxonUpdate, "updateStatus" | "matchMethod"> | null;
  /** Also render the match method as its own hint. */
  showMethod?: boolean;
  /** Use the shorter status wording, for narrow table columns. */
  compact?: boolean;
  className?: string;
}

/**
 * The taxonomic-update status, as shown on every surface.
 *
 * In compact form the status and method prose are combined into one hint, so
 * a table row carries a single toggle rather than two.
 */
export function TaxonStatusBadge({
  update,
  showMethod = false,
  compact = false,
  className = "",
}: TaxonStatusBadgeProps) {
  const descriptions = useCodeDescriptions();

  if (!update?.updateStatus) {
    return (
      <span className="text-deep-mocha-400 dark:text-deep-mocha-600">—</span>
    );
  }

  const { updateStatus, matchMethod } = update;
  const tone = toneForStatus(updateStatus);

  if (compact) {
    const statusText = describeCode(updateStatus, "status", descriptions);
    const methodText = describeCode(matchMethod, "method", descriptions);
    const combined = [statusText, methodText].filter(Boolean).join(" ");
    return (
      <CodeHint
        code={updateStatus}
        kind="status"
        label={statusShortLabel(updateStatus)}
        description={combined || null}
        tone={tone}
        className={className}
      />
    );
  }

  return (
    <span className={`inline-flex flex-wrap items-start gap-1.5 ${className}`}>
      <CodeHint
        code={updateStatus}
        kind="status"
        label={statusLabel(updateStatus)}
        tone={tone}
      />
      {showMethod && matchMethod ? (
        <CodeHint code={matchMethod} kind="method" variant="text" />
      ) : null}
    </span>
  );
}

export default CodeHint;
