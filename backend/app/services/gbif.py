from .model import SpeciesTaxonomy

GBIF_HOST = "https://api.gbif.org/v1/species"


class GbifTaxonSearch:
    """
    Service for searching GBIF taxon names.
    """

    def __init__(self):
        """
        Initialize the GbifTaxonSearch service.
        """
        self.host = GBIF_HOST

    async def search(self, query: str) -> SpeciesTaxonomy | None:
        """
        Search for taxon names in GBIF.

        Check if the result is empty, and if so, return an empty dictionary.
        """
        url = f"{self.host}?name={query}&offset=0&limit=1"
        response = await self.client.get(url)

        if response.status_code != 200:
            raise Exception(
                f"Error fetching data from GBIF: {response.text}"
            )

        data = response.json()
        if not data.get("results"):
            return None

        # Extract the first result
        first_result = data["results"][0]
        gbif_key = first_result.get("key")
        redlist_category = await self.get_redlist_status(gbif_key)
        taxon = SpeciesTaxonomy.from_json(
            first_result, redlist_category
        )

        return taxon

    async def get_redlist_status(
        self, gbif_key: int | None
    ) -> str | None:
        """
        Get the Red List status for a given GBIF key.
        """
        if not gbif_key:
            return None

        url = f"{self.host}/{gbif_key}/iucnRedListCategory"
        response = await self.client.get(url)

        if response.status_code != 200:
            raise Exception(
                f"Error fetching Red List status from GBIF: {response.text}"
            )

        data = response.json()
        return data.get("status")
