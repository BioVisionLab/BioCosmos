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

  // keep active tab in sync with the current pathname so the highlight
  // updates when navigation occurs outside this component
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
            `bg-gradient-to-r from-emerald-100 via-teal-100 to-cyan-100 text-black border-transparent ` +
            `dark:from-emerald-900 dark:via-teal-900 dark:to-cyan-900 dark:text-white`
          }
          role="tablist"
        >
          {navItems.map((tab) => {
            const containerIsGradient = Boolean(activeTab);
            const textColor = containerIsGradient
              ? "text-black dark:text-white hover:opacity-50"
              : "text-gray-600 dark:text-gray-300 hover:bg-gray-200/70 dark:hover:bg-gray-700/70";

            const isActive = activeTab === tab.id;

            const activeItemClass =
              isActive && containerIsGradient
                ? "scale-105 ring-1 ring-white/20 dark:ring-white/10 bg-white/30 dark:bg-white/12"
                : "";

            const classes = `${baseBtn} ${textColor} ${
              isActive ? activeItemClass : ""
            } first:ml-1 last:mr-1`;

            if (tab.href) {
              return (
                <Link
                  href={tab.href}
                  key={tab.id}
                  id={`tab-${tab.id}`}
                  className={classes}
                  role="tab"
                  aria-controls={`tabpanel-${tab.id}`}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <span>{tab.label}</span>
                </Link>
              );
            }

            return (
              <button
                id={`tab-${tab.id}`}
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={classes}
                role="tab"
                aria-controls={`tabpanel-${tab.id}`}
                tabIndex={activeTab === tab.id ? 0 : -1}
              >
                {isActive && (
                  <svg
                    className="w-6 h-6"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden
                  >
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                )}
                <span>{tab.label}</span>
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
