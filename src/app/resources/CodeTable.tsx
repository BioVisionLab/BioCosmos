import { toneClasses, type CodeTone } from "@/lib/codeTone";

export interface CodeTableRow {
  key: string;
  /** The label as it appears on a specimen badge. */
  label: string;
  description: string;
  /**
   * When set, the label is rendered as a pill in the same colour the badge
   * uses, so a reader can match a verdict here to one on a species page by
   * sight rather than by reading.
   */
  tone?: CodeTone;
}

/**
 * A two-column reference table of codes and what they mean.
 *
 * Shared by the taxonomy and coordinate sections so the two vocabularies
 * are presented identically — they are the same kind of claim about a
 * record, and reading one should teach you how to read the other.
 */
export default function CodeTable({
  head,
  rows,
}: {
  head: [string, string];
  rows: CodeTableRow[];
}) {
  return (
    // Two columns from `sm` up, and one stacked label-then-description pair
    // below it.
    //
    // It used to be a table at every width, with a 28rem floor and a
    // `whitespace-nowrap` label column, inside a page that gives a 375px phone
    // about 279px. The label could not wrap and the description had nowhere
    // left to go, so the two ran into each other and the box scrolled
    // sideways. Stacking is the only fix that removes the collision rather
    // than shrinking it.
    //
    // The cost: `display: block` drops the table semantics for assistive
    // technology at phone width. `scope="row"` is kept, so each row still
    // reads as a term and its definition — which is the right reading at that
    // size, and better than serving a duplicate <dl> to everyone.
    <div className="overflow-x-auto">
      <table className="w-full sm:min-w-md text-left text-sm border-collapse">
        {/* Redundant once every row carries its own label. */}
        <thead className="hidden sm:table-header-group">
          <tr className="border-b border-deep-mocha-300 dark:border-deep-mocha-700">
            <th
              scope="col"
              className="py-2 pr-4 font-semibold whitespace-nowrap"
            >
              {head[0]}
            </th>
            <th scope="col" className="py-2 font-semibold">
              {head[1]}
            </th>
          </tr>
        </thead>
        <tbody className="block sm:table-row-group">
          {rows.map((row) => (
            <tr
              key={row.key}
              className="block sm:table-row border-b border-deep-mocha-200/70 dark:border-deep-mocha-800 align-top"
            >
              <th
                scope="row"
                className="block sm:table-cell pt-3 pb-1 sm:py-2 sm:pr-4 text-left font-normal sm:whitespace-nowrap"
              >
                {row.tone ? (
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses(row.tone)}`}
                  >
                    {row.label}
                  </span>
                ) : (
                  row.label
                )}
              </th>
              <td className="block sm:table-cell pb-3 sm:py-2">
                {row.description}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
