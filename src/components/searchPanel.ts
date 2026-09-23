/**
 * The one container every search mode sits in: text, semantic and image.
 *
 * The three used to be three different boxes — a solid green card for text,
 * and a spinning green-to-cyan gradient border for the other two — so
 * switching tabs changed the colour of everything around the field as well
 * as the field itself. They now all wear the text search's green card and
 * differ only in what is inside.
 *
 * The search is the hero's one action, and the green fill is what lifts it
 * off the graph paper: the only filled block in the hero, set flat, with no
 * shadow.
 *
 * `h-full`: SearchSwitcher stacks every mode in one grid cell, so the cell is
 * as tall as the tallest mode and each panel stretches to it — switching tabs
 * no longer changes the height of the box. The bottom margin lives on that
 * grid, since a margin on a full-height panel would overflow it.
 */
export const SEARCH_PANEL =
  "w-full h-full max-w-2xl mx-auto p-6 rounded-3xl border-2 border-hunter-green-300 bg-hunter-green-200 dark:border-hunter-green-700 dark:bg-hunter-green-900";
