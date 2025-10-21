import React from "react";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  return (
    <div className="flex flex-col min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      {/* Main Content - Putting container back on main */}
      <main className="flex-grow container mx-auto px-4 py-8">
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
      <footer className="bg-gray-200 dark:bg-gray-800 py-4 text-center text-sm text-gray-600 dark:text-gray-400">
        © {new Date().getFullYear()} biocosmos. All rights reserved.
        {/* Add other footer links here */}
      </footer>

      {/* Render the Chatbot Panel (uses fixed positioning) */}
      {/* <ChatbotPanel /> */}
    </div>
  );
};

export default Layout;
