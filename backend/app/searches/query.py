import logging

logger = logging.getLogger(__name__)


class SearchResults:
    def __init__(self, results):
        self.results = results

    def __len__(self):
        return len(self.results)

    def __getitem__(self, index):
        return self.results[index]

    def __iter__(self):
        return iter(self.results)

    def __repr__(self):
        return f"SearchResults({self.results})"

    def has_results(self) -> bool:
        """Check if the search results contain any valid data."""
        return (
            self.results
            and self.results.get("ids")
            and self.results["ids"][0]
            and self.results.get("metadatas")
            and self.results["metadatas"][0]
            and self.results.get("distances")
            and self.results["distances"][0]
        )

    def find_best_hit(self):
        """Find the best hit per species based on the lowest distance."""
        best_hits_per_species = {}
        if self.has_results():
            ids = self.results["ids"][0]
            metadata_list = self.results["metadatas"][0]
            distances = self.results["distances"][0]

            for i in range(len(ids)):
                metadata = metadata_list[i]
                distance = distances[i]
                hit_id = ids[i]
                if (
                    metadata
                    and "species_folder" in metadata
                    and "image_filename" in metadata
                ):
                    species_folder = metadata["species_folder"]
                    image_filename = metadata["image_filename"]
                    # Keep track of the best hit (lowest distance) for each species_folder
                    if (
                        species_folder not in best_hits_per_species
                        or distance
                        < best_hits_per_species[species_folder][
                            "distance"
                        ]
                    ):
                        best_hits_per_species[species_folder] = {
                            "distance": distance,
                            "best_image_filename": image_filename,
                            "id": hit_id,
                        }
                else:
                    logger.warning(
                        f"Hit {hit_id} missing 'species_folder' or 'image_filename' in metadata: {metadata}"
                    )
        else:
            logger.info(
                "ChromaDB returned no results or results in unexpected format for image search."
            )

        # 4. Extract results (same logic as text search)
        sorted_species = sorted(
            best_hits_per_species.items(),
            key=lambda item: item[1]["distance"],
        )
        unique_results = [
            {
                "species_folder": species_folder,
                "best_image_filename": data["best_image_filename"],
            }
            for species_folder, data in sorted_species
        ]
        logger.info(
            f"Returning {len(unique_results)} unique species results from image search."
        )
        return unique_results
