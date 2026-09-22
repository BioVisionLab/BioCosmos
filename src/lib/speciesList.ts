const INITIAL_SPECIES = [
  "agrias_narcissus",
  "athyma_libnites",
  "danaus_melanippus",
  "euploea_eleusina",
  "nessaea_hewitsonii",
  "zeuxidia_ameythystus",
  "panacea_prola",
  "charaxes_dilutus",
  "agrias_phalcidon",
  "ypthima_doleta",
];

// Get an initial list of species.
// Request image thumbnails from API/taxon/${speciesName}/thumbnail

export function getSpeciesList(): string[] {
  // Shuffle a copy, not INITIAL_SPECIES itself: `.sort()` sorts in place, so
  // shuffling the module-level array made every later call depend on every
  // earlier one.
  const shuffled = [...INITIAL_SPECIES].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, 6).sort();
}
