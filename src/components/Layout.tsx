import React from "react";
import Link from "next/link";
import HeaderClient from "./HeaderClient";
import ChatbotPanel from "./ChatbotPanel";
import ImageSearchWidget from "./ImageSearchWidget";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  // Example: Define current taxonomy for links (could come from context/props later)
  const currentFamily = "Nymphalidae"; // Example
  // const currentGenus = "Danaus"; // Example (might not always be available)

  return (
    <div className="flex flex-col min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      {/* Use the HeaderClient component */}
      {/* <HeaderClient /> */}

      {/* Main Content - Putting container back on main */}
      <main className="flex-grow container mx-auto px-4 py-8">
        {" "}
        {/* Restored container mx-auto, kept px-4 (container adds padding, but explicit px-4 is fine too) */}
        <div className="flex flex-col md:flex-row gap-8">
          {" "}
          {/* Removed max-w-7xl mx-auto */}
          {/* Sidebar Area */}
          {/* Reduced width on medium+ */}
          <aside className="w-full md:w-56 flex-shrink-0">
            {" "}
            {/* Changed from md:w-64 */}
            {
              /* Sticky sidebar for medium+ screens */
              <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow sticky top-24">
                <h3 className="text-lg font-semibold mb-4 text-gray-700 dark:text-gray-300">
                  Taxonomy
                </h3>
                <nav>
                  <ul className="space-y-1 text-sm">
                    <li>
                      {/* Class Level */}
                      <Link href="/class/insecta" legacyBehavior={false}>
                        <span className="hover:underline cursor-pointer">
                          Class: Insecta
                        </span>
                      </Link>
                      {/* Start Nested List for Orders within this Class */}
                      <ul className="mt-1 pl-4 space-y-1">
                        <li>
                          {/* Order Level */}
                          <Link
                            href="/order/lepidoptera"
                            legacyBehavior={false}
                          >
                            <span className="font-semibold hover:underline cursor-pointer">
                              Order: Lepidoptera
                            </span>
                          </Link>
                          {/* Start Nested List for Families within this Order */}
                          <ul className="mt-1 pl-4 space-y-1">
                            <li>
                              {/* Family Level */}
                              <Link
                                href={`/family/${currentFamily}`}
                                legacyBehavior={false}
                              >
                                <span className="text-green-700 dark:text-green-400 hover:underline cursor-pointer">
                                  Family: {currentFamily}
                                </span>
                              </Link>
                              {/* Genus/Species links could potentially be nested further here if needed */}
                            </li>
                            <li>
                              {/* Another Family Example */}
                              <span className="text-gray-500">
                                Family: Papilionidae
                              </span>
                            </li>
                          </ul>{" "}
                          {/* End Families list */}
                        </li>{" "}
                        {/* End Order li */}
                        {/* Add other Orders here within the Class ul */}
                      </ul>{" "}
                      {/* End Orders list */}
                    </li>{" "}
                    {/* End Class li */}
                    {/* Add other Classes here */}
                  </ul>
                </nav>
              </div> /*}
            {/* Render Image Search Widget */
            }
            <ImageSearchWidget />
          </aside>
          {/* Page Content Area */}
          {/* Takes remaining space on medium+ */}
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
      <ChatbotPanel />
    </div>
  );
};

export default Layout;
