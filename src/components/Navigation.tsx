"use client";

import { Menu, X } from "lucide-react";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

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
    "inline-flex h-9 items-center justify-center px-5 lg:px-6 rounded-full text-sm lg:text-base font-semibold transition-all";

  // The gradient the mobile hamburger and the mobile theme toggle share.
  const mobileSurface =
    "bg-gradient-to-r from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 " +
    "dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800";

  const pillClasses =
    `flex items-center gap-1 p-1.5 rounded-full backdrop-blur-lg ` +
    `bg-gradient-to-r from-hunter-green-200 via-pacific-blue-200 to-frozen-water-200 text-black border-transparent ` +
    `dark:from-hunter-green-800 dark:via-pacific-blue-800 dark:to-frozen-water-800 dark:text-white`;

  return (
    // The same 1600px shell and gutter as <main> in Layout, so the nav's
    // right edge lines up with the page column at every width instead of
    // sitting a fixed distance from the screen edge.
    <div className="relative z-[1000] mx-auto flex w-full max-w-[1600px] flex-col items-end px-4 pt-4 sm:px-6 lg:px-8">
      {/* Mobile: hamburger button */}
      <div className="md:hidden flex items-center gap-2">
        {/* Reachable without opening the menu: the theme is page chrome,
            not a destination. */}
        <div className={`flex h-11 w-11 items-center justify-center rounded-lg backdrop-blur-lg [&>button]:h-full [&>button]:w-full [&>button]:rounded-lg ${mobileSurface}`}>
          <ThemeToggle />
        </div>
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className={`flex h-11 w-11 items-center justify-center rounded-lg backdrop-blur-lg ${mobileSurface}`}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
        >
          {menuOpen ? (
            <X className="w-6 h-6" aria-hidden="true" />
          ) : (
            <Menu className="w-6 h-6" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Mobile: vertical dropdown */}
      {menuOpen && (
        <div className="md:hidden absolute top-full right-0 w-full px-4 sm:px-6 mt-2 py-2">
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
      <nav aria-label="Main" className="hidden md:flex items-center">
        {/* These are links to routes, not tabs: no tablist/tab roles, and
            the current page is marked with aria-current instead. That also
            leaves room for the theme toggle, which is not a destination and
            could not have lived inside a tablist. */}
        <div className={pillClasses}>
          {navItems.map((tab) => {
            const isActive = activeTab === tab.id;
            const textColor = "text-black dark:text-white";
            const outerClasses = `${baseBtn} ${textColor} relative`;
            const showOval =
              hoveredTab !== null ? hoveredTab === tab.id : isActive;
            const bgSpanClasses = `absolute inset-0 rounded-full transition-opacity pointer-events-none ${
              showOval ? "opacity-100" : "opacity-0"
            } bg-white/30 dark:bg-white/12`;

            return (
              <Link
                href={tab.href}
                key={tab.id}
                id={`nav-${tab.id}`}
                className={outerClasses}
                aria-current={isActive ? "page" : undefined}
                onClick={() => setActiveTab(tab.id)}
                onMouseEnter={() => setHoveredTab(tab.id)}
                onMouseLeave={() => setHoveredTab(null)}
              >
                <span className={bgSpanClasses} aria-hidden />
                <span className="relative z-10">{tab.label}</span>
              </Link>
            );
          })}

          {/* A rule, because the links wear pill-shaped hover ovals and a
              round button at the end of that row would otherwise read as a
              fifth, oddly-shaped tab. */}
          <span
            aria-hidden
            className="mx-1.5 h-5 w-px bg-black/15 dark:bg-white/20"
          />
          <ThemeToggle />
        </div>
      </nav>
    </div>
  );
}
