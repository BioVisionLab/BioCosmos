"""The GBIF registry endpoints institution resolution reads.

Two public registries are involved:

- GRSciColl, the Global Registry of Scientific Collections, which records
  institutions by code with their name, country and homepage.
- The GBIF organization registry, which records who published each dataset.

Every call is memoized: many codes share a dataset or a candidate, and one
resolution run should ask about each at most once.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_API_URL = "https://api.gbif.org/v1"
DEFAULT_TIMEOUT_SECONDS = 20.0


class RegistryError(Exception):
    """The registry could not be reached or answered with an error."""


class LookupMatch(StrEnum):
    """GRSciColl's own verdict on a lookup, as `institutionMatch.matchType`."""

    EXACT = "EXACT"
    FUZZY = "FUZZY"
    EXPLICIT_MAPPING = "EXPLICIT_MAPPING"
    NONE = "NONE"


@dataclass(frozen=True)
class RegistryInstitution:
    key: str
    code: str | None
    name: str
    country: str | None = None
    homepage: str | None = None
    active: bool = True


@dataclass(frozen=True)
class LookupResult:
    match: LookupMatch
    institution_key: str | None = None


@dataclass(frozen=True)
class Publisher:
    key: str
    name: str
    country: str | None = None
    homepage: str | None = None


class Registry(Protocol):
    """What the resolver needs from GBIF; a fake stands in for it in tests."""

    def lookup(
        self,
        institution_code: str,
        dataset_key: str | None,
        institution_id: str | None,
        owner_institution_code: str | None,
    ) -> LookupResult: ...

    def institutions_by_code(self, code: str) -> list[RegistryInstitution]: ...

    def institution(self, key: str) -> RegistryInstitution | None: ...

    def dataset_publisher(self, dataset_key: str) -> Publisher | None: ...


def _web_url(value: Any) -> str | None:
    """The first http(s) URL in a registry homepage field, which may be a list."""
    candidates = value if isinstance(value, list) else [value]
    for candidate in candidates:
        if isinstance(candidate, str):
            url = candidate.strip()
            if url.lower().startswith(("http://", "https://")):
                return url
    return None


def _country(record: dict) -> str | None:
    for field in ("address", "mailingAddress"):
        address = record.get(field) or {}
        if address.get("country"):
            return address["country"]
    return None


def _institution(record: dict) -> RegistryInstitution:
    return RegistryInstitution(
        key=record["key"],
        code=record.get("code"),
        name=record["name"],
        country=_country(record),
        homepage=_web_url(record.get("homepage")),
        active=bool(record.get("active", True)),
    )


def _memoized[T](function: Callable[..., T]) -> Callable[..., T]:
    """Thread-safe memoization; the resolver calls the registry from a pool."""
    cache: dict[tuple, T] = {}
    lock = threading.Lock()

    def wrapper(*args: Any) -> T:
        with lock:
            if args in cache:
                return cache[args]
        value = function(*args)
        with lock:
            cache[args] = value
        return value

    return wrapper


class GbifRegistry:
    """HTTP client for the GBIF registry, with retries on throttling."""

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = session or self._default_session()
        self.lookup = _memoized(self._lookup)
        self.institutions_by_code = _memoized(self._institutions_by_code)
        self.institution = _memoized(self._institution)
        self.dataset_publisher = _memoized(self._dataset_publisher)
        self._organization = _memoized(self._fetch_organization)

    @staticmethod
    def _default_session() -> requests.Session:
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
        session.headers["User-Agent"] = "instharmonize (BioCosmos)"
        return session

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        """GET a registry path; None on 404, RegistryError on anything else."""
        try:
            response = self.session.get(
                f"{self.api_url}/{path}", params=params, timeout=self.timeout
            )
        except requests.RequestException as error:
            raise RegistryError(f"GBIF registry request failed: {error}") from error
        if response.status_code == 404:
            return None
        if not response.ok:
            raise RegistryError(f"GBIF registry returned {response.status_code} for {path}")
        try:
            return response.json()
        except ValueError as error:
            raise RegistryError(f"GBIF registry returned invalid JSON for {path}") from error

    def _lookup(
        self,
        institution_code: str,
        dataset_key: str | None,
        institution_id: str | None,
        owner_institution_code: str | None,
    ) -> LookupResult:
        params = {
            "institutionCode": institution_code,
            "datasetKey": dataset_key,
            "institutionId": institution_id,
            "ownerInstitutionCode": owner_institution_code,
        }
        body = self._get(
            "grscicoll/lookup", {name: value for name, value in params.items() if value}
        )
        match = (body or {}).get("institutionMatch") or {}
        try:
            match_type = LookupMatch(match.get("matchType", "NONE"))
        except ValueError:
            match_type = LookupMatch.NONE
        entity = match.get("entityMatched") or {}
        return LookupResult(match=match_type, institution_key=entity.get("key"))

    def _institutions_by_code(self, code: str) -> list[RegistryInstitution]:
        body = self._get("grscicoll/institution", {"code": code, "limit": 50})
        return [_institution(record) for record in (body or {}).get("results", [])]

    def _institution(self, key: str) -> RegistryInstitution | None:
        body = self._get(f"grscicoll/institution/{key}")
        if body is None or body.get("deleted"):
            return None
        return _institution(body)

    def _dataset_publisher(self, dataset_key: str) -> Publisher | None:
        dataset = self._get(f"dataset/{dataset_key}")
        organization_key = (dataset or {}).get("publishingOrganizationKey")
        if not organization_key:
            return None
        return self._organization(organization_key)

    def _fetch_organization(self, key: str) -> Publisher | None:
        body = self._get(f"organization/{key}")
        if body is None:
            return None
        return Publisher(
            key=key,
            name=body.get("title", ""),
            country=body.get("country"),
            homepage=_web_url(body.get("homepage")),
        )
