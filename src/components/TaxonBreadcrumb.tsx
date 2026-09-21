import Link from "next/link";

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
      className="text-sm mt-2 mb-8 text-deep-mocha-600 dark:text-deep-mocha-400 border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white/70 dark:bg-deep-mocha-800/70 backdrop-blur py-1 px-3 w-fit max-w-full rounded-full"
    >
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => (
          <li
            key={`${item.label}-${index}`}
            className="flex items-center gap-2"
          >
            {index > 0 ? (
              <span aria-hidden="true" className="text-deep-mocha-400">
                &gt;
              </span>
            ) : null}
            {item.href ? (
              <Link
                href={item.href}
                className={`hover:underline ${item.italic ? "italic" : ""}`}
              >
                {item.label}
              </Link>
            ) : (
              <span
                aria-current="page"
                className={`text-deep-mocha-800 dark:text-deep-mocha-200 ${
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
