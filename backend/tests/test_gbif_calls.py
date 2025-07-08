from app.services.gbif import GbifTaxonSearch


import pytest


@pytest.mark.asyncio
async def test_gbif_search():
    service = GbifTaxonSearch()
    result = await service.search("danaus plexippus")
    assert result is not None
    assert result.species == "Danaus plexippus"
    assert result.redlist_category == "LEAST_CONCERN"
    await service.close()
