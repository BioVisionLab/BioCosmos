"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useRef, useTransition } from "react";

import PaginationControls from "@/components/PaginationControls";

/**
 * The pagination under a higher taxon's species grid.
 *
 * The page lives in the URL (`?page=`) and the grid is rendered on the
 * server, so a page of species can be linked to and the grid needs no client
 * fetch of its own. The outgoing page stays on screen, dimmed, until the next
 * one arrives: these routes have no loading.tsx to fall back on.
 */
export default function TaxonSpeciesPager({
  heading,
  page,
  totalPages,
  total,
  perPage,
  children,
}: {
  /** Kept inside the scroll target, so a page change lands on it. */
  heading: ReactNode;
  page: number;
  totalPages: number;
  total: number;
  perPage: number;
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const top = useRef<HTMLDivElement>(null);

  const goTo = (next: number) => {
    const params = new URLSearchParams(searchParams.toString());

    // The first page is the taxon's own URL, not a second copy of it.
    if (next <= 1) params.delete("page");
    else params.set("page", String(next));

    const query = params.toString();

    startTransition(() => {
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
    });

    // Controls under a tall grid would otherwise leave the reader looking at
    // the bottom of the new page.
    const box = top.current?.getBoundingClientRect();

    if (box && box.top < 0) {
      top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div ref={top} className="scroll-mt-4">
      {heading}
      <div
        aria-busy={pending || undefined}
        className={`transition-opacity ${pending ? "opacity-50" : ""}`}
      >
        {children}
      </div>
      <PaginationControls
        currentPage={page}
        totalPages={totalPages}
        totalItems={total}
        itemsPerPage={perPage}
        label="species"
        onPageChange={goTo}
      />
    </div>
  );
}
