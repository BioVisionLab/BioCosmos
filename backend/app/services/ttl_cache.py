"""A bounded, least-recently-set memo for answers from external APIs.

Shared by the clients that call third-party services (CrossRef, NCBI), so a
page view repeated within the TTL costs nothing upstream. Entries live in
process memory: a restart empties the cache, and it refills as pages are read.
"""

import time
from collections import OrderedDict


class TtlCache[T]:
    """Entries expire after ``ttl`` seconds, or a per-entry TTL given to
    ``set``; past ``maxsize`` the oldest-set entry is dropped."""

    def __init__(self, ttl: float, maxsize: int):
        self.ttl = ttl
        self.maxsize = maxsize
        self._entries: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: T, ttl: float | None = None) -> None:
        self._entries.pop(key, None)
        lifetime = self.ttl if ttl is None else ttl
        self._entries[key] = (time.monotonic() + lifetime, value)
        while len(self._entries) > self.maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
