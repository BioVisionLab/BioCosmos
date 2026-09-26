"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import PaginationControls from "@/components/PaginationControls";
import { NoData } from "@/components/NoData";

export interface DataTableColumn<Row> {
  key: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /** Present on sortable columns. */
  sortValue?: (row: Row) => string | number;
  numeric?: boolean;
}

type SortState = { key: string; direction: "asc" | "desc" };

/**
 * A client-side table with column sorting, a text filter and pagination.
 *
 * The same shell as the institutions table (`ProvidersTable`), generalized so
 * the country and per-country species tables share one implementation.
 * Filtering or re-sorting returns to page one, so the reader never lands on a
 * page past the end of a shorter result.
 */
export default function DataTable<Row>({
  rows,
  columns,
  rowKey,
  filterText,
  filterLabel,
  initialSort,
  pageSize = 25,
  itemLabel,
  emptyText,
}: {
  rows: Row[];
  columns: DataTableColumn<Row>[];
  rowKey: (row: Row) => string;
  /** The text a row is matched against by the filter box. */
  filterText: (row: Row) => string;
  filterLabel: string;
  initialSort: SortState;
  pageSize?: number;
  /** Plural noun for the pagination summary, e.g. "countries". */
  itemLabel: string;
  emptyText: string;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortState>(initialSort);
  const [currentPage, setCurrentPage] = useState(1);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? rows.filter((row) => filterText(row).toLowerCase().includes(needle))
      : rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return filtered;
    const value = column.sortValue;
    const sign = sort.direction === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const left = value(a);
      const right = value(b);
      const order =
        typeof left === "number" && typeof right === "number"
          ? left - right
          : String(left).localeCompare(String(right));
      return order * sign;
    });
  }, [rows, query, sort, columns, filterText]);

  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
  const page = Math.min(currentPage, totalPages);
  const pageRows = visible.slice((page - 1) * pageSize, page * pageSize);

  const toggleSort = (column: DataTableColumn<Row>) => {
    setCurrentPage(1);
    setSort((previous) =>
      previous.key === column.key
        ? {
            key: column.key,
            direction: previous.direction === "asc" ? "desc" : "asc",
          }
        : // Numbers usually want the largest first; names want A to Z.
          { key: column.key, direction: column.numeric ? "desc" : "asc" },
    );
  };

  if (rows.length === 0) {
    return (
      <div className="p-8">
        <NoData text={emptyText} />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="w-full sm:w-80">
          <span className="sr-only">{filterLabel}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCurrentPage(1);
            }}
            placeholder={filterLabel}
            className="w-full rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/70 dark:bg-deep-mocha-800/60 px-3 py-2 text-sm text-deep-mocha-900 dark:text-white placeholder:text-deep-mocha-400 focus:outline-none focus:ring-2 focus:ring-pacific-blue-500"
          />
        </label>
        <p
          className="text-sm text-deep-mocha-600 dark:text-deep-mocha-400 tabular-nums"
          aria-live="polite"
        >
          {visible.length === rows.length
            ? `${rows.length.toLocaleString("en-US")} ${itemLabel}`
            : `${visible.length.toLocaleString("en-US")} of ${rows.length.toLocaleString("en-US")} ${itemLabel}`}
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-deep-mocha-100/70 dark:bg-deep-mocha-800/70 text-deep-mocha-700 dark:text-deep-mocha-300">
            <tr>
              {columns.map((column) => {
                const active = sort.key === column.key;
                const ariaSort = active
                  ? sort.direction === "asc"
                    ? "ascending"
                    : "descending"
                  : "none";
                const Icon = !active
                  ? ArrowUpDown
                  : sort.direction === "asc"
                    ? ArrowUp
                    : ArrowDown;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={column.sortValue ? ariaSort : undefined}
                    className={`px-4 py-3 font-semibold ${column.numeric ? "text-right" : ""}`}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column)}
                        className={`inline-flex items-center gap-1 cursor-pointer hover:text-deep-mocha-900 dark:hover:text-white ${column.numeric ? "flex-row-reverse" : ""}`}
                      >
                        {column.header}
                        <Icon
                          aria-hidden="true"
                          className={`h-3.5 w-3.5 ${active ? "" : "opacity-40"}`}
                        />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-deep-mocha-200 dark:divide-deep-mocha-700">
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-6 text-center text-deep-mocha-500 dark:text-deep-mocha-400"
                >
                  Nothing matches &ldquo;{query}&rdquo;.
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr
                  key={rowKey(row)}
                  className="bg-white/40 dark:bg-deep-mocha-900/30"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`px-4 py-3 ${
                        column.numeric
                          ? "text-right tabular-nums text-deep-mocha-700 dark:text-deep-mocha-300"
                          : "text-deep-mocha-900 dark:text-white"
                      }`}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <PaginationControls
        currentPage={page}
        totalPages={totalPages}
        totalItems={visible.length}
        itemsPerPage={pageSize}
        label={itemLabel}
        onPageChange={setCurrentPage}
      />
    </div>
  );
}
