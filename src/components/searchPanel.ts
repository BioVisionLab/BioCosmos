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
 */
export const SEARCH_PANEL =
  "w-full max-w-2xl mx-auto mb-6 p-6 rounded-3xl border-2 border-hunter-green-300 bg-hunter-green-200 dark:border-hunter-green-700 dark:bg-hunter-green-900";
