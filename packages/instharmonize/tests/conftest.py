from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from instharmonize.gbif import (
    LookupMatch,
    LookupResult,
    Publisher,
    RegistryError,
    RegistryInstitution,
)


@dataclass
class FakeRegistry:
    """An in-memory GBIF registry; `lookups` is keyed on (code, dataset_key)."""

    lookups: dict[tuple[str, str | None], LookupResult] = field(default_factory=dict)
    by_code: dict[str, list[RegistryInstitution]] = field(default_factory=dict)
    publishers: dict[str, Publisher] = field(default_factory=dict)
    failing: bool = False
    calls: list[tuple] = field(default_factory=list)

    def _check(self, *call: object) -> None:
        self.calls.append(call)
        if self.failing:
            raise RegistryError("offline")

    def lookup(self, institution_code, dataset_key, institution_id, owner_institution_code):
        self._check("lookup", institution_code, dataset_key)
        return self.lookups.get(
            (institution_code, dataset_key), LookupResult(match=LookupMatch.NONE)
        )

    def institutions_by_code(self, code):
        self._check("by_code", code)
        return self.by_code.get(code, [])

    def institution(self, key):
        self._check("institution", key)
        for candidates in self.by_code.values():
            for candidate in candidates:
                if candidate.key == key:
                    return candidate
        return None

    def dataset_publisher(self, dataset_key):
        self._check("publisher", dataset_key)
        return self.publishers.get(dataset_key)


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()
