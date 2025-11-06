const INITIAL_SPECIES = [
  "anaeomorpha_splendida",
  "agrias_narcissus",
  "athyma_libnites",
  "danaus_gilippus",
  "euploea_eleusina",
  "nessaea_hewitsonii",
  "zeuxidia_ameythystus",
  "panacea_prola",
  "charaxes_subornatus",
  "agrias_phalcidon",
  "ypthima_doleta",
];

// Get an initial list of species.
// Request image thumbnails from API/taxon/${speciesName}/thumbnail

export function getSpeciesList(): string[] {
  // We shuffle the initial species array to get a random selection each time
  // return six random species from the list
  const sorted_list = INITIAL_SPECIES.sort(() => 0.5 - Math.random());
  return sorted_list.slice(0, 6).sort();
}
