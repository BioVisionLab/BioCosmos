'use client';

import * as React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

export function ThemeToggle() {
  const { setTheme, theme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  // Ensure the component is mounted on the client before rendering UI
  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Render a placeholder or null on the server/initial render
    // to prevent hydration mismatch
    return <div className="w-9 h-9"></div>; // Placeholder with size
  }

  return (
    <button
      onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
      className="inline-flex items-center justify-center rounded-md p-2 hover:bg-deep-mocha-200 dark:hover:bg-deep-mocha-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-green-500"
      aria-label="Toggle theme"
    >
      {theme === 'light' ? (
        <Sun className="h-5 w-5 text-deep-mocha-700 dark:text-deep-mocha-300" />
      ) : (
        <Moon className="h-5 w-5 text-deep-mocha-700 dark:text-deep-mocha-300" />
      )}
    </button>
  );
} 