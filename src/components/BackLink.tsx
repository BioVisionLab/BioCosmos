import Link from "next/link";
import { ArrowLeft } from "lucide-react";

/**
 * The "← Back" link that opens a page.
 *
 * Every page used to hand-roll its own: some above the title, some below it,
 * some floated right of it, in `blue-600` on one page and `pacific-blue-600`
 * on the next. One component so there is one answer — always the first thing
 * on the page, left-aligned above the title, in the theme's link colour.
 */
export default function BackLink({
  href = "/",
  label = "Back to Home",
}: {
  href?: string;
  label?: string;
}) {
  return (
    <div className="mb-4">
      <Link
        href={href}
        className="group inline-flex items-center gap-1.5 text-sm font-medium text-pacific-blue-700 hover:text-pacific-blue-800 dark:text-pacific-blue-400 dark:hover:text-pacific-blue-300 transition-colors"
      >
        <ArrowLeft
          aria-hidden="true"
          className="h-4 w-4 transition-transform group-hover:-translate-x-0.5"
        />
        {label}
      </Link>
    </div>
  );
}
