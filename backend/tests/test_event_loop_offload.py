"""Blocking DuckDB, model and LLM work stays off the event loop.

FastAPI serves every request from one event loop, so a blocking call made on
it stalls all the others. Each test records the thread the blocking step ran
on and checks it was not the loop's.
"""

import asyncio
import inspect
import threading
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from fastapi import Request

from app.query import higher_taxa, taxon_data
from app.query.higher_taxa import FamilyOverview, HigherTaxonRepository
from app.query.taxon_data import TaxonSearch
from app.routers import data_stats, db_search, ml_search, morphospace, species_data
from app.services.col import ColTaxonSearch


class ThreadRecorder:
    """Callables that note the thread they ran on, then return `value`."""

    def __init__(self):
        self.threads: list[int] = []

    def returning(self, value):
        return _Recorded(self, value)


class _Recorded:
    def __init__(self, recorder: ThreadRecorder, value):
        self.recorder = recorder
        self.value = value

    def __call__(self, *args, **kwargs):
        self.recorder.threads.append(threading.get_ident())

        return self.value


async def _loop_thread() -> int:
    return threading.get_ident()


async def _search_on_loop(service: ColTaxonSearch) -> tuple[int, dict | None]:
    return threading.get_ident(), await service.search("danaus plexippus")


def test_col_search_runs_in_a_worker_thread():
    recorder = ThreadRecorder()
    service = ColTaxonSearch.__new__(ColTaxonSearch)
    service.search_sync = recorder.returning({"species": "Danaus plexippus"})

    loop_thread, taxon = asyncio.run(_search_on_loop(service))

    assert taxon == {"species": "Danaus plexippus"}
    assert recorder.threads and loop_thread not in recorder.threads


async def _overview_on_loop(overview: FamilyOverview) -> tuple[int, dict | None]:
    return threading.get_ident(), await overview.overview()


async def _no_classification() -> None:
    return None


def test_higher_taxon_overview_builds_in_worker_threads(monkeypatch):
    recorder = ThreadRecorder()
    monkeypatch.setattr(higher_taxa.PAYLOAD_CACHE, "get", MagicMock(return_value=None))
    put = MagicMock()
    monkeypatch.setattr(higher_taxa.PAYLOAD_CACHE, "put", put)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(duck_db=object()))
    )
    overview = FamilyOverview(cast(Request, request), "Nymphalidae")
    monkeypatch.setattr(
        overview, "_held_members", recorder.returning([{"image_count": 1}])
    )
    monkeypatch.setattr(
        overview, "_payload", recorder.returning({"key": "nymphalidae"})
    )
    monkeypatch.setattr(overview, "_classification", _no_classification)

    loop_thread, payload = asyncio.run(_overview_on_loop(overview))

    assert payload == {"key": "nymphalidae"}
    assert len(recorder.threads) == 2
    assert loop_thread not in recorder.threads
    put.assert_called_once()


def test_overview_skips_the_classification_without_members(monkeypatch):
    monkeypatch.setattr(higher_taxa.PAYLOAD_CACHE, "get", MagicMock(return_value=None))
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(duck_db=object()))
    )
    overview = FamilyOverview(cast(Request, request), "Nymphalidae")
    classification = MagicMock()
    monkeypatch.setattr(
        HigherTaxonRepository, "harmonized_available", lambda _self: False
    )
    monkeypatch.setattr(overview, "_classification", classification)

    assert asyncio.run(overview.overview()) is None
    classification.assert_not_called()


# The threads FakeSummarizer was called on, one entry per call.
SUMMARY_CALLS: list[int] = []


class FakeSummarizer:
    """Stands in for AiSummary; records the thread of each call."""

    def __init__(self, client):
        self.client = client

    def summarize_text(self, prompt: str) -> str:
        SUMMARY_CALLS.append(threading.get_ident())

        return "A summary."


async def _taxonomy() -> dict:
    return {"species": "Danaus plexippus"}


async def _summarize_twice(search: TaxonSearch) -> tuple[int, str | None, str | None]:
    first = await search.generate_summary()
    second = await search.generate_summary()

    return threading.get_ident(), first, second


def test_summary_runs_off_the_loop_and_is_cached(monkeypatch):
    SUMMARY_CALLS.clear()
    monkeypatch.setattr(taxon_data, "AiSummary", FakeSummarizer)
    taxon_data.SUMMARY_CACHE.clear()
    search = TaxonSearch(cast(Request, MagicMock()), "danaus_plexippus")
    monkeypatch.setattr(search, "_get_taxonomy", _taxonomy)
    monkeypatch.setattr(search, "_get_traits", lambda: None)

    loop_thread, first, second = asyncio.run(_summarize_twice(search))

    assert first == second == "A summary."
    assert len(SUMMARY_CALLS) == 1
    assert loop_thread not in SUMMARY_CALLS


# Handlers whose work is all blocking and that await nothing. As plain `def`
# FastAPI runs them in its threadpool; as `async def` they would block the loop.
THREADPOOL_HANDLERS = [
    data_stats.get_taxon_counts,
    data_stats.get_embedding_stats,
    data_stats.get_country_diversity_stats,
    data_stats.get_country_species,
    db_search.search_db,
    ml_search.search_text,
    morphospace.get_species_morphospace,
    morphospace.get_scope_morphospace,
    species_data.fetch_species_specimen_info,
]


def test_blocking_handlers_run_in_the_threadpool():
    for handler in THREADPOOL_HANDLERS:
        assert not inspect.iscoroutinefunction(handler), handler.__name__
