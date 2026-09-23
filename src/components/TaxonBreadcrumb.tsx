import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface Crumb {
  label: string;
  /** Absent on the last crumb, which is the page you are already on. */
  href?: string;
  italic?: boolean;
}

/**
 * The trail of ranks above the taxon on show.
 *
 * The pill the species page has worn for a while, lifted out of it so the
 * family and genus pages cannot drift from it. Markup and `Link` only — no
 * server-only import — because the species page is a client component and
 * has to be able to use this too.
 *
 * It gains what the inline version never had: a labelled `nav`, a real
 * ordered list, and `aria-current` on the crumb you are standing on.
 */
export default function TaxonBreadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      // mt-2: clearance under the navigation, which sits in normal flow
      // directly above. Carried by the component rather than by each page, so
      // the species, family and genus trails cannot drift apart again.
      //
      // rounded-2xl rather than rounded-full: on one line the 16px radius of
      // a 32px-tall bar is already a pill, but when a long species name wraps
      // the trail onto a second line, a full radius pinched the corners in
      // towards the text and the side padding visibly collapsed. A fixed
      // radius keeps the same inset on every line.
      className="text-sm mt-2 mb-8 text-deep-mocha-600 dark:text-deep-mocha-400 border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur py-1.5 px-4 w-fit max-w-full rounded-2xl"
    >
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 leading-5">
        {items.map((item, index) => (
          <li
            key={`${item.label}-${index}`}
            // min-w-0 so a single crumb longer than the bar (a trinomial on a
            // phone) wraps inside itself instead of overflowing the pill.
            className="flex min-w-0 items-center gap-1.5"
          >
            {index > 0 ? (
              <ChevronRight
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0 text-deep-mocha-400 dark:text-deep-mocha-500"
              />
            ) : null}
            {item.href ? (
              <Link
                href={item.href}
                className={`min-w-0 break-words hover:text-pacific-blue-700 hover:underline dark:hover:text-pacific-blue-400 ${
                  item.italic ? "italic" : ""
                }`}
              >
                {item.label}
              </Link>
            ) : (
              <span
                aria-current="page"
                className={`min-w-0 break-words font-medium text-deep-mocha-800 dark:text-deep-mocha-200 ${
                  item.italic ? "italic" : ""
                }`}
              >
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
