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
    // Tables are the one thing allowed to be wider than the page; it scrolls
    // in its own box rather than widening the document on a phone.
    <div className="overflow-x-auto">
      <table className="w-full min-w-md text-left text-sm border-collapse">
        <thead>
          <tr className="border-b border-deep-mocha-300 dark:border-deep-mocha-700">
            <th scope="col" className="py-2 pr-4 font-semibold whitespace-nowrap">
              {head[0]}
            </th>
            <th scope="col" className="py-2 font-semibold">
              {head[1]}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-deep-mocha-200/70 dark:border-deep-mocha-800 align-top"
            >
              <th
                scope="row"
                className="py-2 pr-4 font-normal whitespace-nowrap"
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
              <td className="py-2">{row.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
