/*
Each publication type gets a ColorBrewer Dark2 fill, in palette order, with
whichever of black or white text clears WCAG AA (4.5:1) on it; the weakest is
black on #7570b3 at 4.7:1. The fill is the same in both themes, so a label
keeps its contrast in dark mode.

As a chart bar, every fill clears the 3:1 non-text minimum against the
near-black page (the lowest is #666666 at 3.5:1), but #66a61e (3.0:1) and
#e6ab02 (2.1:1) do not against white. In light mode each bar segment is
therefore outlined in its fill darkened to 68%, which clears 4.3:1 or more
against white.
*/
export type PublicationTypeKey =
  | "journal-article"
  | "dataset"
  | "book"
  | "preprint"
  | "proceedings"
  | "dissertation"
  | "other";

export const publicationTypes: Record<
  PublicationTypeKey,
  { label: string; plural: string; fill: string; stroke: string; text: string }
> = {
  "journal-article": {
    label: "Journal article",
    plural: "Journal articles",
    fill: "bg-[#1b9e77]",
    stroke: "ring-[#126b51]",
    text: "text-black",
  },
  dataset: {
    label: "Dataset",
    plural: "Datasets",
    fill: "bg-[#d95f02]",
    stroke: "ring-[#944101]",
    text: "text-black",
  },
  book: {
    label: "Book or chapter",
    plural: "Books and chapters",
    fill: "bg-[#7570b3]",
    stroke: "ring-[#504c7a]",
    text: "text-black",
  },
  preprint: {
    label: "Preprint",
    plural: "Preprints",
    fill: "bg-[#e7298a]",
    stroke: "ring-[#9d1c5e]",
    text: "text-black",
  },
  proceedings: {
    label: "Proceedings or report",
    plural: "Proceedings and reports",
    fill: "bg-[#66a61e]",
    stroke: "ring-[#457114]",
    text: "text-black",
  },
  dissertation: {
    label: "Dissertation",
    plural: "Dissertations",
    fill: "bg-[#e6ab02]",
    stroke: "ring-[#9c7401]",
    text: "text-black",
  },
  other: {
    label: "Other",
    plural: "Other",
    fill: "bg-[#666666]",
    stroke: "ring-[#454545]",
    text: "text-white",
  },
};

/* Bottom to top in a stacked bar, and the order of the summary tiles. */
export const publicationTypeOrder: PublicationTypeKey[] = [
  "journal-article",
  "dataset",
  "book",
  "preprint",
  "proceedings",
  "dissertation",
  "other",
];

/* CrossRef work types, by the category they are shown under. */
const crossrefTypeCategories: Record<string, PublicationTypeKey> = {
  "journal-article": "journal-article",
  dataset: "dataset",
  book: "book",
  "book-chapter": "book",
  "edited-book": "book",
  monograph: "book",
  "posted-content": "preprint",
  "proceedings-article": "proceedings",
  report: "proceedings",
  dissertation: "dissertation",
};

export function publicationTypeKey(type?: string): PublicationTypeKey {
  return (type && crossrefTypeCategories[type]) || "other";
}

export type TypeCounts = Record<PublicationTypeKey, number>;

export function emptyCounts(): TypeCounts {
  return Object.fromEntries(
    publicationTypeOrder.map((key) => [key, 0]),
  ) as TypeCounts;
}

export function countTotal(counts: TypeCounts): number {
  return publicationTypeOrder.reduce((sum, key) => sum + counts[key], 0);
}
