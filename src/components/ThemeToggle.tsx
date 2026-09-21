"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

/**
 * Light/dark toggle, sized to sit inside the navigation pill.
 *
 * It paints no background gradient of its own: it lives on the pill, which
 * already carries one, and a second gradient on top of that read as a
 * detached copy of the navbar rather than a control within it. The hover
 * wash is the same one the nav links use, so the toggle and the links
 * respond alike.
 */
export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  // Avoid rendering theme-dependent UI until after client mount, so the
  // server-rendered markup always matches the first client render.
  React.useEffect(() => {
    setMounted(true);
  }, []);

  // The same box the button occupies, so the pill does not change width
  // when the toggle mounts.
  if (!mounted) {
    return <div aria-hidden className="h-9 w-9 shrink-0 rounded-full" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="group relative h-9 w-9 shrink-0 overflow-hidden rounded-full bg-white/20 transition-colors hover:bg-white/35 focus:outline-none focus-visible:ring-2 focus-visible:ring-hunter-green-600 dark:bg-white/8 dark:hover:bg-white/15 dark:focus-visible:ring-frozen-water-300"
    >
      {/* Sun and moon cross-fade with a subtle rotate/scale. */}
      <span className="relative flex h-full w-full items-center justify-center">
        <Sun
          aria-hidden
          className={`absolute h-5 w-5 text-black/80 transition-all duration-500 ease-in-out ${
            isDark
              ? "opacity-0 rotate-90 scale-50"
              : "opacity-100 rotate-0 scale-100"
          }`}
        />
        <Moon
          aria-hidden
          className={`absolute h-5 w-5 text-white/90 transition-all duration-500 ease-in-out ${
            isDark
              ? "opacity-100 rotate-0 scale-100"
              : "opacity-0 -rotate-90 scale-50"
          }`}
        />
      </span>
    </button>
  );
}
