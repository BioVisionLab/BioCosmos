"""Unit tests for the agent-search result cache."""

from app.services.agent_cache import AgentSearchCache, normalize_query, paginate


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def rows(count):
    return [{"imgId": str(index)} for index in range(count)]


def test_normalize_query_ignores_case_and_whitespace():
    assert normalize_query("  Blue   Morpho\n") == "blue morpho"


def test_entries_expire_after_ttl():
    clock = FakeClock()
    cache = AgentSearchCache(ttl_seconds=10, clock=clock)
    entry = cache.put("blue", rows(1))

    clock.now = 10
    assert cache.get(entry.search_id) is entry

    clock.now = 10.5
    assert cache.get(entry.search_id) is None
    assert cache.get_by_query("blue") is None


def test_least_recently_used_entry_is_evicted():
    cache = AgentSearchCache(max_entries=2)
    first = cache.put("first", rows(1))
    second = cache.put("second", rows(1))
    cache.get(first.search_id)

    cache.put("third", rows(1))

    assert cache.get(first.search_id) is first
    assert cache.get(second.search_id) is None
    assert cache.get_by_query("second") is None


def test_repeated_query_replaces_previous_entry():
    cache = AgentSearchCache()
    old = cache.put("blue", rows(1))
    new = cache.put("Blue", rows(2))

    assert cache.get(old.search_id) is None
    assert cache.get_by_query("blue") is new


def test_paginate_edges():
    data = rows(5)

    assert paginate(data, 0, 2) == (data[:2], True)
    assert paginate(data, 3, 2) == (data[3:], False)
    assert paginate(data, 10, 2) == ([], False)
    assert paginate([], 0, 35) == ([], False)
