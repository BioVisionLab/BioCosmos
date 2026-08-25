import React from "react";
import Navigation from "./Navigation";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  return (
    <div className="flex flex-col min-h-screen bg-deep-mocha-100 dark:bg-deep-mocha-900 text-deep-mocha-900 dark:text-deep-mocha-100">
      {/* Use the HeaderClient component */}
      {/* <HeaderClient /> */}

      <Navigation />

      {/* Main Content - Putting container back on main */}
      <main className="flex-grow container mx-auto px-4 py-4">
        {" "}
        {/* Restored container mx-auto, kept px-4 (container adds padding, but explicit px-4 is fine too) */}
        <div className="flex flex-col">
          <div className="flex-1 min-w-0">
            {" "}
            {/* flex-1 allows it to grow, min-w-0 prevents overflow */}
            {children}
          </div>
        </div>
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
