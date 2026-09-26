"use client";

import Link from "next/link";

import DataTable, { type DataTableColumn } from "@/components/DataTable";
import { countryHref, type CountryDiversityRow } from "@/lib/countryDiversity";

const count = (value: number) => value.toLocaleString("en-US");

const COLUMNS: DataTableColumn<CountryDiversityRow>[] = [
  {
    key: "country",
    header: "Country",
    sortValue: (row) => row.countryName,
    cell: (row) => (
      <Link
        href={countryHref(row.countryCode)}
        className="text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
      >
        {row.countryName}
      </Link>
    ),
  },
  {
    key: "code",
    header: "ISO code",
    sortValue: (row) => row.countryCode,
    cell: (row) => <span className="font-mono text-xs">{row.countryCode}</span>,
  },
  {
    key: "species",
    header: "Species",
    numeric: true,
    sortValue: (row) => row.speciesCount,
    cell: (row) => count(row.speciesCount),
  },
  {
    key: "images",
    header: "Images",
    numeric: true,
    sortValue: (row) => row.imageCount,
    cell: (row) => count(row.imageCount),
  },
  {
    key: "imputed",
    header: "Imputed images",
    numeric: true,
    sortValue: (row) => row.imputedImageCount,
    cell: (row) => count(row.imputedImageCount),
  },
];

const filterText = (row: CountryDiversityRow) =>
  `${row.countryName} ${row.countryCode}`;
const rowKey = (row: CountryDiversityRow) => row.countryCode;

export default function CountryTable({
  rows,
}: {
  rows: CountryDiversityRow[];
}) {
  return (
    <DataTable
      rows={rows}
      columns={COLUMNS}
      rowKey={rowKey}
      filterText={filterText}
      filterLabel="Filter by country name or code"
      initialSort={{ key: "species", direction: "desc" }}
      itemLabel="countries"
      emptyText="No country data available."
    />
  );
}
