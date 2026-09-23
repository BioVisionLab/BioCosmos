"use client";

import { useMemo, useState } from "react";

import PaginationControls from "@/components/PaginationControls";
import { NoData } from "@/components/NoData";

const PAGE_SIZE = 20;

export default function ProvidersTable({
  institutionCounts,
}: {
  institutionCounts: Record<string, number> | null;
}) {
  const [currentPage, setCurrentPage] = useState(1);

  const rows = useMemo(() => {
    const entries = Object.entries(institutionCounts ?? {});
    const total = entries.reduce((sum, [, count]) => sum + count, 0);
    return entries
      .map(([institution, count]) => ({
        institution,
        count,
        percentage: total > 0 ? ((count / total) * 100).toFixed(2) + "%" : "0%",
      }))
      .sort((a, b) => b.count - a.count);
  }, [institutionCounts]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const page = Math.min(currentPage, totalPages);
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (rows.length === 0) {
    return (
      <div className="p-8">
        <NoData text="No institution data available." />
      </div>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-deep-mocha-200 dark:border-deep-mocha-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-deep-mocha-100/70 dark:bg-deep-mocha-800/70 text-deep-mocha-700 dark:text-deep-mocha-300">
            <tr>
              <th className="px-4 py-3 font-semibold">Institution</th>
              <th className="px-4 py-3 font-semibold text-right">Images</th>
              <th className="px-4 py-3 font-semibold text-right">Share</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-deep-mocha-200 dark:divide-deep-mocha-700">
            {pageRows.map((row) => (
              <tr
                key={row.institution}
                className="bg-white/40 dark:bg-deep-mocha-900/30"
              >
                <td className="px-4 py-3 text-deep-mocha-900 dark:text-white">
                  {row.institution}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-deep-mocha-700 dark:text-deep-mocha-300">
                  {row.count.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-deep-mocha-700 dark:text-deep-mocha-300">
                  {row.percentage}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PaginationControls
        currentPage={page}
        totalPages={totalPages}
        totalItems={rows.length}
        itemsPerPage={PAGE_SIZE}
        label="institutions"
        onPageChange={setCurrentPage}
      />
    </div>
  );
}
