"use client";

import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";

import { safeWebUrl } from "@/lib/imageMetadata";
import type { InstitutionInfo } from "@/lib/metaStats";
import PaginationControls from "@/components/PaginationControls";
import { NoData } from "@/components/NoData";

const PAGE_SIZE = 20;

function InstitutionCell({
  code,
  info,
}: {
  code: string;
  info: InstitutionInfo | undefined;
}) {
  if (!info) {
    return <span>{code}</span>;
  }
  // Registry data is not trusted blindly: only http(s) becomes a link.
  const homepage = safeWebUrl(info.homepage);
  return (
    <div className="flex flex-col gap-0.5">
      {homepage ? (
        <a
          href={homepage}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-start gap-1 font-medium underline decoration-deep-mocha-300 underline-offset-2 hover:text-pacific-blue-700 dark:decoration-deep-mocha-600 dark:hover:text-pacific-blue-300"
        >
          {info.name}
          <ExternalLink
            aria-hidden="true"
            className="mt-0.5 h-3.5 w-3.5 shrink-0"
          />
          <span className="sr-only">(opens institution website)</span>
        </a>
      ) : (
        <span className="font-medium">{info.name}</span>
      )}
      {/* A record with no code is keyed on its written-out name; repeating
          it adds nothing. */}
      {code !== info.name && (
        <span className="font-mono text-xs text-deep-mocha-500 dark:text-deep-mocha-400">
          {code}
        </span>
      )}
    </div>
  );
}

export default function ProvidersTable({
  institutionCounts,
  institutionDirectory,
}: {
  institutionCounts: Record<string, number> | null;
  institutionDirectory?: Record<string, InstitutionInfo> | null;
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
                  <InstitutionCell
                    code={row.institution}
                    info={institutionDirectory?.[row.institution]}
                  />
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
