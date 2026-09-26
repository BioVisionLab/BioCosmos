"use client";

import Link from "next/link";

import DataTable, { type DataTableColumn } from "@/components/DataTable";
import type { CountrySpeciesRow } from "@/lib/countryDiversity";
import { speciesUrlFromName } from "@/lib/names";

const count = (value: number) => value.toLocaleString("en-US");

const COLUMNS: DataTableColumn<CountrySpeciesRow>[] = [
  {
    key: "species",
    header: "Species",
    sortValue: (row) => row.species,
    cell: (row) => (
      <Link
        href={`/species/${speciesUrlFromName(row.species)}`}
        className="italic text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
      >
        {row.species}
      </Link>
    ),
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

const filterText = (row: CountrySpeciesRow) => row.species;
const rowKey = (row: CountrySpeciesRow) => row.species;

export default function CountrySpeciesTable({
  rows,
}: {
  rows: CountrySpeciesRow[];
}) {
  return (
    <DataTable
      rows={rows}
      columns={COLUMNS}
      rowKey={rowKey}
      filterText={filterText}
      filterLabel="Filter by species or genus"
      initialSort={{ key: "images", direction: "desc" }}
      itemLabel="species"
      emptyText="No species recorded for this country."
    />
  );
}
