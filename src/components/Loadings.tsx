import React from "react";

import { ButterflyIcon, type IconSize } from "./ui/icons";

/** The stroke tier for a glyph drawn `px` wide; see `IconSize`. */
function iconSizeFor(px: number): IconSize {
  if (px <= 32) return "sm";
  if (px <= 56) return "md";
  return "lg";
}

function ImageLoading({ size, msg }: { size: number; msg?: string }) {
  // The placeholder keeps the full `size` box so nothing shifts when the image
  // arrives, but the glyph inside is drawn smaller: a stroked icon at 400px
  // turns into a stencil. Inline rather than an <img>, so it takes the theme's
  // icon colours and each instance still pulses on its own.
  const glyph = Math.round(size * 0.6);
  return (
    <div className="flex flex-col items-center justify-center text-center gap-1">
      <div
        role="img"
        aria-label="Loading"
        className="mx-auto flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        {/* Sized by a wrapper: `size` is arbitrary, not a Tailwind step. */}
        <span
          className="animate-pulse opacity-80 [&>svg]:h-full [&>svg]:w-full"
          style={{ width: glyph, height: glyph }}
        >
          <ButterflyIcon size={iconSizeFor(glyph)} />
        </span>
      </div>
      <TextLoading msg={msg || "Loading image"} />
    </div>
  );
}

function TextLoading({ msg }: { msg: string }) {
  return (
    <p className="mt-1 flex items-baseline justify-center gap-2 text-xs leading-none text-deep-mocha-500 mx-auto">
      {/* make the message a bit smaller than before */}
      <span className="text-sm">{msg}</span>
      <span className="flex items-center justify-center gap-1">
        <span className="-ml-1 w-1 h-1 rounded-full bg-deep-mocha-400 dark:bg-deep-mocha-500 animate-bounce [animation-delay:0ms]" />
        <span className="w-1 h-1 rounded-full bg-deep-mocha-400 dark:bg-deep-mocha-500 animate-bounce [animation-delay:150ms]" />
        <span className="w-1 h-1 rounded-full bg-deep-mocha-400 dark:bg-deep-mocha-500 animate-bounce [animation-delay:300ms]" />
      </span>
    </p>
  );
}

export { ImageLoading, TextLoading };
