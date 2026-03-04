"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navigation() {
  const navItems = [
    { id: "home", label: "Home", href: "/" },
    { id: "collections", label: "Collections", href: "/collections" },
    { id: "resources", label: "Resources", href: "/resources" },
    { id: "about", label: "About", href: "/about" },
  ];

  const [activeTab, setActiveTab] = useState(navItems[0].id);
  const [hoveredTab, setHoveredTab] = useState<string | null>(null);

  const pathname = usePathname();

  useEffect(() => {
    if (!pathname) return;
    const p = pathname;
    let id = "home";
    if (p === "/") id = "home";
    else if (p.startsWith("/collections")) id = "collections";
    else if (p.startsWith("/resources")) id = "resources";
    else if (p.startsWith("/about")) id = "about";
    setActiveTab(id);
  }, [pathname]);

  const baseBtn =
    "inline-flex items-center justify-center px-8 py-1 rounded-full text-1xl font-semibold transition-all";

  return (
    <div className="flex flex-col items-end w-full">
      <div className="flex items-center mt-4 mr-8">
        <div
          className={
            `flex items-center gap-4 p-2 rounded-full backdrop-blur-lg ` +
            `bg-gradient-to-r from-emerald-200 via-teal-200 to-cyan-200 text-black border-transparent ` +
            `dark:from-emerald-800 dark:via-teal-800 dark:to-cyan-800 dark:text-white`
          }
          role="tablist"
        >
          {navItems.map((tab) => {
            const isActive = activeTab === tab.id;
            const textColor = "text-black dark:text-white";

            const outerClasses = `${baseBtn} ${textColor} relative first:ml-1 last:mr-1`;

            const showOval = hoveredTab !== null ? hoveredTab === tab.id : isActive;

            const bgSpanClasses = `absolute inset-0 rounded-full transition-opacity pointer-events-none ${
              showOval ? "opacity-100" : "opacity-0"
            } bg-white/30 dark:bg-white/12`;

            if (tab.href) {
              return (
                <Link
                  href={tab.href}
                  key={tab.id}
                    id={`tab-${tab.id}`}
                    className={outerClasses}
                    role="tab"
                    aria-controls={`tabpanel-${tab.id}`}
                    tabIndex={activeTab === tab.id ? 0 : -1}
                    onClick={() => setActiveTab(tab.id)}
                    onMouseEnter={() => setHoveredTab(tab.id)}
                    onMouseLeave={() => setHoveredTab(null)}
                  >
                    <span className={bgSpanClasses} aria-hidden />
                    <span className="relative z-10">{tab.label}</span>
                  </Link>
              );
            }

            return (
              <button
                id={`tab-${tab.id}`}
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                onMouseEnter={() => setHoveredTab(tab.id)}
                onMouseLeave={() => setHoveredTab(null)}
                className={outerClasses}
                role="tab"
                aria-controls={`tabpanel-${tab.id}`}
                tabIndex={activeTab === tab.id ? 0 : -1}
              >
                <span className={bgSpanClasses} aria-hidden />
                {isActive && (
                  <svg
                    className="w-6 h-6 relative z-10"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden
                  >
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                )}
                <span className="relative z-10">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 mt-2 rounded-lg w-full">
        {navItems.map((tab) => (
          <div
            key={tab.id}
            id={`tabpanel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab.id}`}
            className={activeTab === tab.id ? "" : "hidden"}
          />
        ))}
      </div>
    </div>
  );
}
