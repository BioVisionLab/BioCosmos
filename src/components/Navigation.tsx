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
  const [menuOpen, setMenuOpen] = useState(false);

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

  // Close mobile menu on route change
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const baseBtn =
    "inline-flex items-center justify-center px-8 py-1 rounded-full text-1xl font-semibold transition-all";

  const pillClasses =
    `flex items-center gap-4 p-2 rounded-full backdrop-blur-lg ` +
    `bg-gradient-to-r from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 text-black border-transparent ` +
    `dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 dark:text-white`;

  return (
    <div className="flex flex-col items-end w-full">
      {/* Mobile: hamburger button */}
      <div className="md:hidden flex items-center mt-4 mr-4">
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className={`p-2 rounded-lg backdrop-blur-lg ${pillClasses.includes("dark:") ? "bg-gradient-to-r from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800" : ""}`}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
        >
          {menuOpen ? (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile: vertical dropdown */}
      {menuOpen && (
        <div className="md:hidden w-full px-4 mt-2">
          <div
            className={
              `flex flex-col gap-2 p-3 rounded-2xl backdrop-blur-lg ` +
              `bg-gradient-to-b from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 text-black border-transparent ` +
              `dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 dark:text-white`
            }
          >
            {navItems.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <Link
                  key={tab.id}
                  href={tab.href}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setMenuOpen(false);
                  }}
                  className={`px-4 py-2 rounded-full text-base font-semibold transition-all ${
                    isActive
                      ? "bg-white/30 dark:bg-white/12"
                      : "hover:bg-white/20 dark:hover:bg-white/8"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Desktop: horizontal pill nav */}
      <div className="hidden md:flex items-center mt-4 mr-8">
        <div className={pillClasses} role="tablist">
          {navItems.map((tab) => {
            const isActive = activeTab === tab.id;
            const textColor = "text-black dark:text-white";
            const outerClasses = `${baseBtn} ${textColor} relative first:ml-1 last:mr-1`;
            const showOval = hoveredTab !== null ? hoveredTab === tab.id : isActive;
            const bgSpanClasses = `absolute inset-0 rounded-full transition-opacity pointer-events-none ${
              showOval ? "opacity-100" : "opacity-0"
            } bg-white/30 dark:bg-white/12`;

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
          })}
        </div>
      </div>
    </div>
  );
}
