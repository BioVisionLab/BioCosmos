'use client';

import * as React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

/* Circular light/dark mode toggle. */
export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  // Avoid rendering theme-dependent UI until after client mount, so the
  // server-rendered markup always matches the first client render.
  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        aria-hidden
        className="absolute top-16 right-4 md:top-20 md:right-8 z-40 h-11 w-11 rounded-full"
      />
    );
  }

  const isDark = resolvedTheme === 'dark';

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="group absolute top-16 right-4 md:top-20 md:right-8 z-40 h-11 w-11 rounded-full overflow-hidden border border-white/40 dark:border-white/10 shadow-sm hover:shadow-md active:scale-90 hover:scale-105 transition-transform duration-300 ease-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-hunter-green-500 dark:focus:ring-offset-deep-mocha-900"
    >
      
      <span
        aria-hidden
        className={`absolute inset-0 backdrop-blur-lg bg-gradient-to-br from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 transition-opacity duration-500 ease-in-out ${
          isDark ? 'opacity-0' : 'opacity-100'
        }`}
      />
      <span
        aria-hidden
        className={`absolute inset-0 backdrop-blur-lg bg-gradient-to-br from-hunter-green-800 via-pacific-blue-800 to-frozen-water-800 transition-opacity duration-500 ease-in-out ${
          isDark ? 'opacity-100' : 'opacity-0'
        }`}
      />

      {/* Icon: sun and moon cross-fade with a subtle rotate/scale */}
      <span className="relative flex h-full w-full items-center justify-center">
        <Sun
          aria-hidden
          className={`absolute h-5 w-5 text-hunter-green-800 transition-all duration-500 ease-in-out ${
            isDark ? 'opacity-0 rotate-90 scale-50' : 'opacity-100 rotate-0 scale-100'
          }`}
        />
        <Moon
          aria-hidden
          className={`absolute h-5 w-5 text-frozen-water-100 transition-all duration-500 ease-in-out ${
            isDark ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'
          }`}
        />
      </span>
    </button>
  );
}
