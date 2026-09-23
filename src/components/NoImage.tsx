import { ImageOff } from "lucide-react";

/**
 * What an image slot shows when it has nothing to show: no record, or a
 * thumbnail that failed to load.
 *
 * Absolutely positioned to fill its container, so it lands dead centre in any
 * image box without that box having to know about it. The parent must be
 * `relative`.
 */
export default function NoImage({ className = "" }: { className?: string }) {
  return (
    <div
      className={`absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-deep-mocha-500 dark:text-deep-mocha-400 pointer-events-none ${className}`}
    >
      <ImageOff aria-hidden="true" className="h-5 w-5" />
      <span>No image</span>
    </div>
  );
}
