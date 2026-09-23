"""In-process cache of agent-search outcomes, served a page at a time."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

SEARCH_TTL_SECONDS = 15 * 60
MAX_CACHED_SEARCHES = 200

_WHITESPACE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Case- and whitespace-insensitive key for repeated queries."""
    return _WHITESPACE.sub(" ", query.strip().lower())


@dataclass
class CachedSearch:
    search_id: str
    query: str
    rows: list[dict]
    warnings: list[dict] = field(default_factory=list)
    created_at: float = 0.0


class AgentSearchCache:
    """TTL + LRU store of ranked agent-search rows.

    Entries are looked up by `search_id` (for "show more") and by normalized
    query (so a reload or a second visitor does not re-run the planner).

    The backend runs a single `fastapi run` worker, so process memory is
    shared by every request. Running more workers would need a shared store.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = SEARCH_TTL_SECONDS,
        max_entries: int = MAX_CACHED_SEARCHES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, CachedSearch] = OrderedDict()
        self._by_query: dict[str, str] = {}

    def put(
        self, query: str, rows: list[dict], warnings: list[dict] | None = None
    ) -> CachedSearch:
        entry = CachedSearch(
            search_id=uuid.uuid4().hex,
            query=query,
            rows=rows,
            warnings=warnings or [],
            created_at=self._clock(),
        )
        key = normalize_query(query)
        with self._lock:
            previous = self._by_query.get(key)
            if previous is not None:
                self._entries.pop(previous, None)
            self._entries[entry.search_id] = entry
            self._by_query[key] = entry.search_id
            while len(self._entries) > self.max_entries:
                _, evicted = self._entries.popitem(last=False)
                self._forget_query(evicted)
        return entry

    def get(self, search_id: str) -> CachedSearch | None:
        with self._lock:
            entry = self._entries.get(search_id)
            if entry is None:
                return None
            if self._expired(entry):
                del self._entries[search_id]
                self._forget_query(entry)
                return None
            self._entries.move_to_end(search_id)
            return entry

    def get_by_query(self, query: str) -> CachedSearch | None:
        with self._lock:
            search_id = self._by_query.get(normalize_query(query))
        return self.get(search_id) if search_id is not None else None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._by_query.clear()

    def _expired(self, entry: CachedSearch) -> bool:
        return self._clock() - entry.created_at > self.ttl_seconds

    def _forget_query(self, entry: CachedSearch) -> None:
        key = normalize_query(entry.query)
        if self._by_query.get(key) == entry.search_id:
            del self._by_query[key]


def paginate(rows: list[dict], offset: int, limit: int) -> tuple[list[dict], bool]:
    """Return one page of rows and whether more remain after it."""
    page = rows[offset : offset + limit]
    return page, offset + len(page) < len(rows)


# Shared by every request in this worker; see AgentSearchCache.
agent_search_cache = AgentSearchCache()
