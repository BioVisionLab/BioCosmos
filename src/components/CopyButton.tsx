"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

function copyBySelection(text: string): boolean {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    area.remove();
  }
}

const defaultClass =
  "inline-flex items-center gap-1 rounded border border-deep-mocha-600/40 px-1.5 py-0.5 text-xs text-deep-mocha-600 hover:bg-deep-mocha-600/10 hover:text-deep-mocha-800 focus-visible:outline-2 focus-visible:outline-pacific-blue-700 dark:text-deep-mocha-300 dark:hover:text-deep-mocha-100 dark:focus-visible:outline-pacific-blue-300";

/** Copies `text` to the clipboard and confirms for a moment. */
function CopyButton({
  text,
  label = "Copy",
  buttonText = "Copy",
  className = defaultClass,
}: {
  text: string;
  /** What is copied, for the button's accessible name. */
  label?: string;
  /** The visible label before copying. */
  buttonText?: string;
  /** Replaces the default look, to sit beside another button. */
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // The async API is missing outside secure contexts (a LAN address over
      // http) and can be denied by the browser; the selection copy still works.
      setCopied(copyBySelection(text));
    }
  };

  const Icon = copied ? Check : Copy;
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={label}
      className={className}
    >
      <Icon aria-hidden="true" className="size-3" />
      <span aria-live="polite">{copied ? "Copied" : buttonText}</span>
    </button>
  );
}

export default CopyButton;
