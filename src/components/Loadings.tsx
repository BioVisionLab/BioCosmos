import React from "react";

function ImageLoading({ size, msg }: { size: number; msg?: string }) {
  // Use a plain <img> here instead of next/image so each placeholder
  // instance behaves independently and keeps its animation until the
  // real thumbnail replaces it.
  return (
    <div className="flex flex-col items-center justify-center text-center gap-1">
      <img
        src="/icons/butterfly.svg"
        alt="Loading"
        width={size}
        height={size}
        className="animate-pulse mx-auto opacity-80"
      />
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
