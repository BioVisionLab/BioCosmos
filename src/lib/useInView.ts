"use client";

import { useEffect, useState } from "react";

/**
 * Observe an element and report once it comes within `rootMargin` of the
 * viewport. `ref` is a callback ref, so it picks the element up whenever it
 * mounts — including after a loading state. The flag latches to `true` and
 * the observer disconnects, so this is meant for one-shot "start loading now"
 * gates rather than visibility tracking.
 *
 * Falls back to reporting `true` immediately where IntersectionObserver is
 * unavailable, so gated content still loads.
 */
export function useInView<T extends HTMLElement = HTMLDivElement>(
  rootMargin = "200px",
): { ref: (node: T | null) => void; inView: boolean } {
  // A callback ref rather than a ref object: callers commonly render a
  // loading state first, so the observed node appears on a later render and
  // an effect keyed on a ref object would never see it.
  const [node, setNode] = useState<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [node, inView, rootMargin]);

  return { ref: setNode, inView };
}
