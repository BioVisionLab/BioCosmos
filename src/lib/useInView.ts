"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Observe an element and report once it comes within `rootMargin` of the
 * viewport. The flag latches to `true` and the observer disconnects, so this
 * is meant for one-shot "start loading now" gates rather than visibility
 * tracking.
 *
 * Falls back to reporting `true` immediately where IntersectionObserver is
 * unavailable, so gated content still loads.
 */
export function useInView<T extends HTMLElement = HTMLDivElement>(
  rootMargin = "200px",
): { ref: React.RefObject<T | null>; inView: boolean } {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return;

    const node = ref.current;
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
  }, [inView, rootMargin]);

  return { ref, inView };
}
