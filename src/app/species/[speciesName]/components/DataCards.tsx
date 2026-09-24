import { Children, type ReactNode } from "react";

// Shared by the Genetics and Traits sections of the Biology tab, so the two
// read as one page rather than two designs stacked on each other.

export const valueClass =
  "font-semibold text-deep-mocha-700 dark:text-deep-mocha-200 text-base sm:text-lg";
export const labelClass =
  "font-normal text-base sm:text-lg text-deep-mocha-700 dark:text-deep-mocha-200";
// Every icon-and-value row, so the cards line up with one another.
export const rowClass = "flex min-w-0 items-center gap-2 px-3 py-1";
// Colour lives in the icon primitive now, so a call site says only how big.
export const commonIconClass = "w-12 h-12 m-2";

/**
 * One category of cards: a heading over a grid that is one column on a phone
 * and two from `sm` up.
 *
 * Renders nothing when every card in it was skipped for lack of data, so a
 * species without, say, host plant records does not show an empty heading.
 */
export function DataSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const cards = Children.toArray(children).filter(Boolean);
  if (cards.length === 0) {
    return null;
  }
  return (
    <section className="mb-8">
      <h3 className="mb-3 border-b border-deep-mocha-300 pb-2 text-xl font-semibold dark:border-deep-mocha-700">
        {title}
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">{cards}</div>
    </section>
  );
}

/**
 * A single card: its name, then the icon-and-value row it renders.
 *
 * `min-w-0` lets long values (host plant families, affinities) wrap inside
 * the grid track instead of stretching it.
 *
 * @param wide Spans both columns, for content that needs the full measure.
 */
export function DataCard({
  title,
  wide = false,
  children,
}: {
  title: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`min-w-0 rounded-xl border border-deep-mocha-200 bg-white/50 py-3 dark:border-deep-mocha-700 dark:bg-deep-mocha-800/40 ${
        wide ? "sm:col-span-2" : ""
      }`}
    >
      <h4 className="mb-2 px-3 text-base font-medium text-deep-mocha-800 sm:text-lg dark:text-deep-mocha-100">
        {title}
      </h4>
      {children}
    </div>
  );
}
