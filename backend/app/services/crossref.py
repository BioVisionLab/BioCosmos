"""A small, polite client for the CrossRef REST API.

The literature tab used to call CrossRef straight from every visitor's
browser: anonymous, uncached, and with no backoff. This client is the single
place the application talks to CrossRef, and follows its etiquette
(https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/):

* Identify the caller. A ``mailto`` parameter and a User-Agent carrying it
  route requests to the "polite" pool. Without one, requests go to the public
  pool, and this client drops to one request at a time.
* Stay inside the advertised limits. In-flight requests are capped by a
  semaphore, and request starts are spaced by the rate CrossRef reports in
  ``x-rate-limit-limit`` / ``x-rate-limit-interval``.
* Back off when told to. A 429 or 503 waits out ``Retry-After`` once, then
  gives up; the caller reports a partial result rather than hammering. A 403
  means CrossRef has blocked the client, and every request then fails fast
  for an hour instead of calling again.
* Page with cursors, never deep offsets, and only when a page was full.
* Ask for as little as possible. ``select`` trims each record to the fields
  the page renders, and results are cached, with concurrent identical
  requests sharing one call.
"""

import asyncio
import logging
import time
from urllib.parse import urlencode

import httpx

from ..configs.config import (
    DEFAULT_LITERATURE_WORK_TYPES,
    CrossrefConfig,
    LiteratureConfig,
)
from .ttl_cache import TtlCache

logger = logging.getLogger(__name__)

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
USER_AGENT = "BioCosmos/0.1"
PROJECT_URL = "https://github.com/agporto/BioCosmos"

# Only what the literature list renders, plus the abstract for matching. Books,
# reports, theses and datasets often have no container title, so their
# publisher stands in for the journal. (`subtype`, which would tell a preprint
# from other posted content, is not a selectable field.)
SELECT_FIELDS = (
    "DOI,type,title,author,issued,published-print,published-online,"
    "volume,issue,page,container-title,publisher,abstract"
)

# The polite pool currently allows 3 concurrent requests at 3 per second; the
# public pool answers with 1 request per second, one at a time. These hold
# until the first response; the rate and the concurrency are then refined
# from its headers.
POLITE_CONCURRENCY = 3
PUBLIC_CONCURRENCY = 1
POLITE_RATE_PER_SECOND = 3.0
PUBLIC_RATE_PER_SECOND = 1.0

REQUEST_TIMEOUT_SECONDS = 10.0
# A Retry-After longer than this is not worth holding a page request open for.
MAX_RETRY_AFTER_SECONDS = 5.0
# After a 403, CrossRef has blocked this client; stay away this long.
BLOCK_COOLDOWN_SECONDS = 60 * 60

# A week: a species' literature grows slowly, and a cached miss costs a reader
# nothing but a newer paper.
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
CACHE_MAX_ENTRIES = 512


class CrossrefError(Exception):
    """CrossRef could not be reached or refused the request."""


# One page of works and the cursor for the next, None when CrossRef gave none.
CrossrefPage = tuple[list[dict], str | None]


def works_filter(work_types: tuple[str, ...], from_year: int | None) -> str:
    """The `filter` value: every work type (CrossRef ORs repeated filters on
    one field), plus a publication-year floor when one is set."""
    filters = [f"type:{work_type}" for work_type in work_types]

    if from_year is not None:
        filters.append(f"from-pub-date:{from_year}-01-01")

    return ",".join(filters)


class CrossrefClient:
    """Search CrossRef works, within its limits and with caching."""

    def __init__(
        self,
        mailto: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        cache: TtlCache[CrossrefPage] | None = None,
        work_types: tuple[str, ...] = DEFAULT_LITERATURE_WORK_TYPES,
        from_year: int | None = None,
    ):
        self.mailto = mailto
        self.filter = works_filter(work_types, from_year)
        self.from_year = from_year
        self._transport = transport
        self._cache = cache or TtlCache(CACHE_TTL_SECONDS, CACHE_MAX_ENTRIES)
        self._concurrency = POLITE_CONCURRENCY if mailto else PUBLIC_CONCURRENCY
        rate = POLITE_RATE_PER_SECOND if mailto else PUBLIC_RATE_PER_SECOND
        self._min_interval = 1.0 / rate
        self._next_start = 0.0
        self._blocked_until = 0.0
        # asyncio primitives belong to the loop they were first used on. The
        # app has one loop, but tests run several, so these are rebuilt when
        # the loop changes rather than created at import.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._pace_lock: asyncio.Lock | None = None
        self._client: httpx.AsyncClient | None = None
        self._inflight: dict[str, asyncio.Future] = {}

    @property
    def user_agent(self) -> str:
        contact = f"; mailto:{self.mailto}" if self.mailto else ""
        return f"{USER_AGENT} ({PROJECT_URL}{contact})"

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if loop is self._loop:
            return
        self._loop = loop
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._pace_lock = asyncio.Lock()
        self._inflight = {}
        # The old client's connections belong to a closed loop; drop it.
        self._client = httpx.AsyncClient(
            transport=self._transport,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )

    def build_url(self, query: str, rows: int, cursor: str | None = None) -> str:
        params = {
            "query.bibliographic": query,
            "rows": str(rows),
            "filter": self.filter,
            "select": SELECT_FIELDS,
            "sort": "relevance",
            "order": "desc",
        }

        if cursor is not None:
            params["cursor"] = cursor

        if self.mailto:
            params["mailto"] = self.mailto
        return f"{CROSSREF_WORKS_URL}?{urlencode(params)}"

    async def search_works(self, query: str, rows: int = 40) -> list[dict]:
        """Return CrossRef work records for a bibliographic query.

        Raises CrossrefError when CrossRef cannot answer; the caller decides
        whether that is fatal or only makes the result partial.
        """
        items, _ = await self._search(self.build_url(query, rows))

        return items

    async def search_works_page(
        self, query: str, rows: int, cursor: str = "*"
    ) -> CrossrefPage:
        """One cursor page of a bibliographic query, and the next cursor.

        Pass ``"*"`` for the first page and the returned cursor for the next.
        A page with fewer than ``rows`` items is the last one.
        """
        return await self._search(self.build_url(query, rows, cursor))

    async def _search(self, url: str) -> CrossrefPage:
        self._bind_loop()
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        # Two readers opening the same species page share one request.
        pending = self._inflight.get(url)
        if pending is not None:
            try:
                return await asyncio.shield(pending)
            except asyncio.CancelledError:
                # The request we were sharing was abandoned by its owner; that
                # is a failed lookup for us, not a cancellation of our own.
                if pending.cancelled():
                    raise CrossrefError("Shared CrossRef request was cancelled.")
                raise

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[url] = future
        try:
            page = await self._fetch(url)
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as error:
            future.set_exception(error)
            # Mark retrieved so a failure nobody else awaited is not logged as
            # "never retrieved".
            future.exception()
            raise
        else:
            self._cache.set(url, page)
            future.set_result(page)
            return page
        finally:
            self._inflight.pop(url, None)

    async def _pace(self) -> None:
        """Space request starts by the advertised rate limit."""
        assert self._pace_lock is not None
        async with self._pace_lock:
            now = time.monotonic()
            wait = self._next_start - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_start = now + self._min_interval

    def _learn_limits(self, response: httpx.Response) -> None:
        """Adopt the limits CrossRef reports: a rate such as 3 requests per
        '1s', and the number of requests allowed in flight at once."""
        self._learn_concurrency(response)
        limit = response.headers.get("x-rate-limit-limit")
        interval = response.headers.get("x-rate-limit-interval", "1s")
        try:
            requests = float(limit) if limit else 0.0
            seconds = float(interval.rstrip("s")) if interval else 1.0
        except ValueError:
            return
        if requests > 0 and seconds > 0:
            self._min_interval = seconds / requests

    def _learn_concurrency(self, response: httpx.Response) -> None:
        try:
            limit = int(response.headers.get("x-concurrency-limit", ""))
        except ValueError:
            return

        if 0 < limit < self._concurrency:
            logger.info(
                f"CrossRef allows {limit} concurrent requests; lowering the cap."
            )
            self._concurrency = limit
            # Requests holding the old semaphore finish under it; every later
            # request waits on the lower cap.
            self._semaphore = asyncio.Semaphore(limit)

    def _check_block(self) -> None:
        if time.monotonic() < self._blocked_until:
            raise CrossrefError("CrossRef has blocked this client; not retrying yet.")

    async def _fetch(self, url: str) -> CrossrefPage:
        assert self._semaphore is not None and self._client is not None
        for attempt in range(2):
            self._check_block()
            async with self._semaphore:
                await self._pace()
                try:
                    response = await self._client.get(url)
                except httpx.HTTPError as error:
                    raise CrossrefError(f"CrossRef request failed: {error}") from error

            self._learn_limits(response)

            if response.status_code == 403:
                self._blocked_until = time.monotonic() + BLOCK_COOLDOWN_SECONDS
                logger.error(
                    "CrossRef answered 403: this client is blocked. Literature "
                    f"searches pause for {BLOCK_COOLDOWN_SECONDS // 60} minutes. Check "
                    "that CROSSREF_MAILTO is set to a monitored address, since "
                    "CrossRef writes to it before blocking."
                )
                raise CrossrefError("CrossRef answered 403 (blocked).")

            if response.status_code in (429, 503) and attempt == 0:
                delay = _retry_after_seconds(response)
                logger.warning(
                    f"CrossRef answered {response.status_code}; retrying in {delay:.1f}s."
                )
                await asyncio.sleep(delay)
                continue
            if response.status_code != 200:
                raise CrossrefError(
                    f"CrossRef answered {response.status_code} for {url}"
                )
            try:
                message = response.json()["message"]

                return message["items"] or [], message.get("next-cursor")
            except (ValueError, KeyError, TypeError) as error:
                raise CrossrefError(f"Unexpected CrossRef response: {error}") from error
        raise CrossrefError("CrossRef is rate limiting requests.")

    def clear_cache(self) -> None:
        self._cache.clear()


def _retry_after_seconds(response: httpx.Response) -> float:
    value = response.headers.get("retry-after", "")
    try:
        seconds = float(value)
    except ValueError:
        seconds = 1.0
    return max(0.0, min(seconds, MAX_RETRY_AFTER_SECONDS))


_shared_client: CrossrefClient | None = None


def get_crossref_client() -> CrossrefClient:
    """The process-wide client, so every request shares one cache and limit."""
    global _shared_client
    if _shared_client is None:
        mailto = CrossrefConfig().mailto
        if not mailto:
            logger.warning(
                "CROSSREF_MAILTO is not set; literature searches will use "
                "CrossRef's anonymous public pool, one request at a time."
            )
        literature = LiteratureConfig()
        _shared_client = CrossrefClient(
            mailto,
            work_types=literature.work_types,
            from_year=literature.from_year,
        )
    return _shared_client
