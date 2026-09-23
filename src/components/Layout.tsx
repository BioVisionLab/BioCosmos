import React from "react";
import Navigation from "./Navigation";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  return (
    // Clipped on x so a full-bleed landing band, which is 100vw and so wider
    // than the page by the scrollbar, cannot open a horizontal scroll.
    <div className="relative flex flex-col min-h-screen overflow-x-clip bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-900 dark:text-deep-mocha-100">
      {/* Use the HeaderClient component */}
      {/* <HeaderClient /> */}

      <Navigation />

      {/*
        One shell width for every page. Tailwind's `container` capped at the
        current breakpoint, so anything past 1536px was letterboxed; this
        keeps growing to 1600px and pages that want to stay narrow (about,
        collections) still cap themselves.
      */}
      <main className="flex-grow w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
        {/* min-w-0 so a wide child (a chart, a table) scrolls itself rather
            than stretching the page. */}
        <div className="flex flex-col min-w-0">{children}</div>
      </main>

      {/* Footer */}
      <footer className="bg-deep-mocha-200 dark:bg-deep-mocha-800 py-4 text-center text-sm text-deep-mocha-600 dark:text-deep-mocha-400">
        © {new Date().getFullYear()} Lepiverse. All rights reserved.
        {/* Add other footer links here */}
      </footer>

      {/* Render the Chatbot Panel (uses fixed positioning) */}
      {/* <ChatbotPanel /> */}
    </div>
  );
};

export default Layout;
