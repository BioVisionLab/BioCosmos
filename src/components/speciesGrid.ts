/**
 * The grid every paged list of species sits in: the text search's species
 * results and the species of a higher taxon.
 *
 * The column count is fixed per breakpoint rather than auto-filled, and every
 * count (2, 3, 4, 6 and 8) divides SPECIES_GRID_PAGE_SIZE, so each row of a
 * full page is full at any width. Only a list's last page can end short.
 */
export const SPECIES_GRID =
  "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3 sm:gap-4";

/** How many species one page of the grid holds. */
export const SPECIES_GRID_PAGE_SIZE = 24;

/** The `sizes` of an image that fills one cell of the grid. */
export const SPECIES_GRID_SIZES =
  "(max-width: 640px) 50vw, (max-width: 768px) 33vw, (max-width: 1024px) 25vw, (max-width: 1280px) 17vw, 12vw";
