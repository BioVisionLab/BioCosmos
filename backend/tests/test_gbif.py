from app.services.gbif import GbifTaxonSearch, GbifPersistData
import pytest


@pytest.mark.asyncio
async def test_gbif_search():
    service = GbifTaxonSearch()
    result = await service.search("danaus plexippus")
    assert result is not None
    assert result.get("species") == "Danaus plexippus"
    assert result.get("redlistCategory") == "LC"
    await service.close()


def test_gbif_entries():
    service = GbifPersistData()
    result = service.count_entries()
    assert result is not None
    assert isinstance(result, int)
