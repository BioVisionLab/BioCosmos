"use client";

import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export interface SearchFieldOption {
  value: string;
  label: string;
}

export interface SearchFieldGroup {
  /** Omitted for options that sit above every group, such as "All Fields". */
  label?: string;
  options: SearchFieldOption[];
}

/**
 * The "Search by" field picker.
 *
 * A native `<select>` opens an OS-drawn popup that ignores the site's colours
 * — white-on-grey in a dark theme, blue highlights in a green one — so this
 * draws its own listbox in the site theme, with the keyboard behaviour of a
 * select: arrows move, Enter or Space picks, Escape closes.
 */
export default function SearchFieldSelect({
  id,
  value,
  onChange,
  groups,
  className = "",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  groups: SearchFieldGroup[];
  className?: string;
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const flat = useMemo(() => groups.flatMap((g) => g.options), [groups]);
  // Index of each group's first option in `flat`, so an option knows its
  // place in the keyboard order without a counter mutated during render.
  const offsets = useMemo(
    () =>
      groups.reduce<number[]>(
        (acc, g, gi) => [
          ...acc,
          gi === 0 ? 0 : acc[gi - 1] + groups[gi - 1].options.length,
        ],
        [],
      ),
    [groups],
  );
  const selectedIndex = Math.max(
    0,
    flat.findIndex((o) => o.value === value),
  );
  const [activeIndex, setActiveIndex] = useState(selectedIndex);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex]);

  const openList = () => {
    setActiveIndex(selectedIndex);
    setOpen(true);
  };

  const choose = (index: number) => {
    const option = flat[index];
    if (option && option.value !== value) onChange(option.value);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
      case "ArrowUp": {
        e.preventDefault();
        if (!open) return openList();
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActiveIndex((i) => Math.min(flat.length - 1, Math.max(0, i + step)));
        break;
      }
      case "Home":
      case "End":
        if (!open) return;
        e.preventDefault();
        setActiveIndex(e.key === "Home" ? 0 : flat.length - 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (open) choose(activeIndex);
        else openList();
        break;
      case "Escape":
        if (open) {
          e.preventDefault();
          setOpen(false);
        }
        break;
      case "Tab":
        setOpen(false);
        break;
    }
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-${activeIndex}` : undefined}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKeyDown}
        className="w-full text-left bg-white/70 dark:bg-deep-mocha-800/60 backdrop-blur border border-deep-mocha-200 dark:border-deep-mocha-700 rounded-xl px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-hunter-green-500/60 shadow-xs hover:border-hunter-green-500/50 hover:shadow-sm transition-all text-deep-mocha-800 dark:text-deep-mocha-100 cursor-pointer font-medium truncate"
      >
        {flat[selectedIndex]?.label}
      </button>
      <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-deep-mocha-500 dark:text-deep-mocha-400">
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </span>

      {open && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          aria-labelledby={id}
          tabIndex={-1}
          className="absolute left-0 z-50 mt-2 min-w-full w-max max-w-[min(20rem,calc(100vw-2rem))] max-h-72 overflow-y-auto rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white dark:bg-deep-mocha-800 py-1 shadow-lg text-left"
        >
          {groups.map((group, gi) => (
            <li key={group.label ?? `group-${gi}`} role="presentation">
              {group.label && (
                <div
                  role="presentation"
                  className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-deep-mocha-500 dark:text-deep-mocha-400"
                >
                  {group.label}
                </div>
              )}
              <ul role="group" aria-label={group.label}>
                {group.options.map((option, oi) => {
                  const i = offsets[gi] + oi;
                  const selected = option.value === value;
                  const active = i === activeIndex;
                  return (
                    <li
                      key={option.value}
                      id={`${listId}-${i}`}
                      data-index={i}
                      role="option"
                      aria-selected={selected}
                      onPointerEnter={() => setActiveIndex(i)}
                      onClick={() => choose(i)}
                      className={`mx-1 flex items-center justify-between gap-3 rounded-lg px-3 py-1.5 text-sm cursor-pointer ${
                        active
                          ? "bg-hunter-green-100 dark:bg-hunter-green-900/70"
                          : ""
                      } ${
                        selected
                          ? "font-semibold text-hunter-green-800 dark:text-hunter-green-200"
                          : "text-deep-mocha-800 dark:text-deep-mocha-100"
                      }`}
                    >
                      {option.label}
                      {selected && (
                        <Check
                          className="h-4 w-4 shrink-0"
                          aria-hidden="true"
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
