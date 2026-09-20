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
import React, {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

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

/** Distance between the trigger and the tooltip, in pixels. */
const TOOLTIP_GAP = 8;
/** How close the tooltip may come to the edge of the window. */
const VIEWPORT_MARGIN = 8;
/** Matches the `max-w-xs` on the panel; used before it has been measured. */
const TOOLTIP_MAX_WIDTH = 288;

interface TooltipPosition {
  top: number;
  left: number;
}

/**
 * Place the tooltip against its trigger, in viewport coordinates.
 *
 * Returns null until the panel has first been measured, so the caller can
 * keep it invisible for that frame rather than letting it flash at the
 * origin.
 */
function useTooltipPosition(
  open: boolean,
  triggerRef: React.RefObject<HTMLElement | null>,
  panelRef: React.RefObject<HTMLElement | null>,
): TooltipPosition | null {
  const [position, setPosition] = useState<TooltipPosition | null>(null);

  useLayoutEffect(() => {
    // Nothing to place while closed, and no need to clear the last position:
    // the panel is unmounted, and the next open re-measures in this same
    // effect, before the browser paints.
    if (!open) return;

    const place = () => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const panel = panelRef.current;
      const width = panel?.offsetWidth ?? TOOLTIP_MAX_WIDTH;
      const height = panel?.offsetHeight ?? 0;

      // Below by default, above when there is no room below but there is
      // above — a hint on the last row of a long table would otherwise open
      // off-screen.
      const below = rect.bottom + TOOLTIP_GAP;
      const fitsBelow = below + height <= window.innerHeight - VIEWPORT_MARGIN;
      const fitsAbove = rect.top - TOOLTIP_GAP - height >= VIEWPORT_MARGIN;
      const top = !fitsBelow && fitsAbove ? rect.top - TOOLTIP_GAP - height : below;

      const left = Math.min(
        Math.max(VIEWPORT_MARGIN, rect.left),
        Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN),
      );
      setPosition({ top, left });
    };

    place();
    // Capture, so scrolling the table the trigger sits in also repositions it.
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, triggerRef, panelRef]);

  return position;
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
 * A code that explains itself on hover.
 *
 * The panel is rendered into a portal on `document.body` and positioned in
 * viewport coordinates. That is what lets it work inside the search results
 * table, which sits in an `overflow-x-auto` that clips vertically too — an
 * absolutely positioned panel inside a cell would be cut off.
 *
 * Hover and keyboard focus open it; a click pins it, which is how it works on
 * touch, where there is no hover.
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
  const panelRef = useRef<HTMLSpanElement>(null);
  const [hovering, setHovering] = useState(false);
  const [pinned, setPinned] = useState(false);
  const descriptions = useCodeDescriptions();

  // Never true on the server, or on the first client render: it takes a
  // pointer or focus event to open. So the portal below, which needs
  // `document`, is only ever reached in the browser.
  const open = hovering || pinned;
  const position = useTooltipPosition(open, triggerRef, panelRef);

  if (!code) return null;

  const visibleLabel = label ?? humanizeCode(code);
  const text = description ?? describeCode(code, kind, descriptions);

  const labelClasses =
    variant === "badge"
      ? `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses(tone)}`
      : "inline-flex items-center gap-1 text-xs text-deep-mocha-600 dark:text-deep-mocha-400";

  // Without prose there is nothing to reveal, so render a plain label rather
  // than a control that does nothing when hovered.
  if (!text) {
    return (
      <span className={`${labelClasses} ${className}`}>{visibleLabel}</span>
    );
  }

  const close = () => {
    setHovering(false);
    setPinned(false);
  };

  return (
    <span className={`inline-flex min-w-0 ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        aria-describedby={open ? panelId : undefined}
        onPointerEnter={(event) => {
          // A touch "pointerenter" fires just before the tap; leave that to
          // the click handler so the tooltip does not open and pin at once.
          if (event.pointerType !== "touch") setHovering(true);
        }}
        onPointerLeave={() => setHovering(false)}
        onFocus={() => setHovering(true)}
        onBlur={close}
        onClick={(event) => {
          // These sit inside table cells that are themselves links.
          event.preventDefault();
          event.stopPropagation();
          setPinned((previous) => !previous);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            // Stop here so a hint inside the specimen modal closes itself
            // without also closing the modal, which listens on the window.
            event.stopPropagation();
            close();
          }
        }}
        className={`${labelClasses} cursor-help transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hunter-green-500 ${
          variant === "text" ? "underline decoration-dotted underline-offset-2" : ""
        }`}
      >
        <span className="truncate">{visibleLabel}</span>
        <Lightbulb className="h-3 w-3 shrink-0 opacity-70" aria-hidden="true" />
      </button>
      {open
        ? createPortal(
            <span
              ref={panelRef}
              id={panelId}
              role="tooltip"
              style={{
                position: "fixed",
                top: position?.top ?? 0,
                left: position?.left ?? 0,
                // Hidden for the frame before it has been measured, so it
                // does not flash in the top-left corner.
                visibility: position ? "visible" : "hidden",
              }}
              className="z-50 flex items-start gap-1.5 border-l-8 border border-deep-mocha-600/40 bg-deep-mocha-100 dark:bg-deep-mocha-800 shadow-lg rounded-lg p-2 max-w-xs text-xs font-normal normal-case leading-normal text-deep-mocha-700 dark:text-deep-mocha-300 pointer-events-none"
            >
              <span>{text}</span>
            </span>,
            document.body,
          )
        : null}
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
 * a table row carries a single trigger rather than two.
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
