"""A small, polite client for NCBI's E-utilities and Datasets APIs.

The genetics tab used to call NCBI Datasets straight from every visitor's
browser: anonymous, uncached, and unable to hold an API key. This client is
the single place the application talks to NCBI, and follows its usage
policies (https://www.ncbi.nlm.nih.gov/books/NBK25497/,
https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/rest-api/):

* Identify the caller. E-utilities requests carry ``tool`` and ``email``;
  every request carries a User-Agent with the contact, and the API key when
  one is configured.
* Stay inside the limits. Without a key NCBI allows 3 requests per second per
  IP, with one 10 (Datasets: 5 and 10). One pacer spaces request starts for
  both services, under the lower limit, and a semaphore caps those in flight.
* Back off when told to. A 429 or 503 waits out ``Retry-After`` once, then
  gives up; the caller reports a partial result rather than hammering.

Answers are not cached here: ``GeneticsSummary`` caches the assembled page,
which is what a repeat visitor asks for.
"""

import asyncio
import logging
import time
from urllib.parse import quote

import httpx

from ..configs.config import NcbiConfig

logger = logging.getLogger(__name__)

EUTILS_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DATASETS_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2"
TOOL_NAME = "BioCosmos"
USER_AGENT = "BioCosmos/0.1"
PROJECT_URL = "https://github.com/agporto/BioCosmos"

CONCURRENCY = 3
# Slightly under the advertised 3 and 10 per second, so clock jitter on
# NCBI's side never tips a burst over the line.
MIN_INTERVAL_WITHOUT_KEY = 1 / 2.8
MIN_INTERVAL_WITH_KEY = 1 / 9

REQUEST_TIMEOUT_SECONDS = 10.0
# A Retry-After longer than this is not worth holding a page request open for.
MAX_RETRY_AFTER_SECONDS = 5.0


class NcbiError(Exception):
    """NCBI could not be reached or refused the request."""


class NcbiClient:
    """Counts and reports from NCBI, within its limits."""

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.email = email
        self._transport = transport
        self._min_interval = (
            MIN_INTERVAL_WITH_KEY if api_key else MIN_INTERVAL_WITHOUT_KEY
        )
        self._next_start = 0.0
        # asyncio primitives belong to the loop they were first used on; see
        # CrossrefClient._bind_loop.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._pace_lock: asyncio.Lock | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def user_agent(self) -> str:
        contact = f"; mailto:{self.email}" if self.email else ""
        return f"{USER_AGENT} ({PROJECT_URL}{contact})"

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if loop is self._loop:
            return
        self._loop = loop
        self._semaphore = asyncio.Semaphore(CONCURRENCY)
        self._pace_lock = asyncio.Lock()
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if self.api_key:
            # Datasets reads the key from this header; E-utilities from the
            # `api_key` parameter added in `nuccore_count`.
            headers["api-key"] = self.api_key
        self._client = httpx.AsyncClient(
            transport=self._transport,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers=headers,
        )

    async def gene_type_counts(self, taxon: str) -> dict[str, int]:
        """Annotated genes of each NCBI gene type; empty for an unannotated
        or unknown taxon."""
        data = await self._get_json(
            f"{DATASETS_URL}/gene/taxon/{quote(taxon, safe='')}/counts"
        )
        report = data.get("report") or data.get("gene_counts") or []
        counts: dict[str, int] = {}
        for item in report:
            gene_type = item.get("gene_type")
            count = item.get("count")
            if isinstance(gene_type, str) and isinstance(count, int) and count > 0:
                counts[gene_type] = count
        return counts

    async def mitogenome_reports(self, taxon: str) -> list[dict]:
        """RefSeq mitochondrial genomes for the taxon and its subspecies."""
        data = await self._get_json(
            f"{DATASETS_URL}/organelle/taxon/{quote(taxon, safe='')}/dataset_report"
        )
        return [
            report
            for report in data.get("reports") or []
            if str(report.get("description", "")).lower() == "mitochondrion"
        ]

    async def reference_genome_reports(self, taxon: str) -> list[dict]:
        """The taxon's designated reference genome assembly, if it has one.

        The RefSeq copy comes first when both exist, and it is the one that
        carries NCBI's annotation. One report is about 4 KB, so only one is
        asked for.
        """
        data = await self._get_json(
            f"{DATASETS_URL}/genome/taxon/{quote(taxon, safe='')}/dataset_report",
            {"filters.reference_only": "true", "page_size": "1"},
        )
        return data.get("reports") or []

    async def genome_assemblies(
        self, taxon: str, page_size: int, *, accessions_only: bool = False
    ) -> tuple[list[dict], int]:
        """Current GenBank assemblies of the taxon, and how many there are.

        GenBank alone, so an assembly and its RefSeq copy count once, and
        current versions alone, so a reassembly does not count twice. With
        `accessions_only`, NCBI returns only accessions, which is all a count
        needs.
        """
        params = {
            "filters.assembly_source": "genbank",
            "filters.assembly_version": "current",
            "page_size": str(page_size),
        }
        if accessions_only:
            params["returned_content"] = "ASSM_ACC"
        data = await self._get_json(
            f"{DATASETS_URL}/genome/taxon/{quote(taxon, safe='')}/dataset_report",
            params,
        )
        reports = data.get("reports") or []
        total = data.get("total_count")
        return reports, total if isinstance(total, int) else len(reports)

    async def nuccore_count(self, term: str) -> int:
        """How many GenBank nucleotide records match an Entrez query."""
        params = {
            "db": "nuccore",
            "term": term,
            "rettype": "count",
            "retmode": "json",
            "tool": TOOL_NAME,
        }
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        data = await self._get_json(EUTILS_ESEARCH_URL, params)
        try:
            return int(data["esearchresult"]["count"])
        except (KeyError, TypeError, ValueError) as error:
            # E-utilities reports a malformed query as a 200 with an
            # `ERROR` field instead of a count.
            raise NcbiError(f"Unexpected esearch response: {data}") from error

    async def _pace(self) -> None:
        """Space request starts by the rate limit."""
        assert self._pace_lock is not None
        async with self._pace_lock:
            now = time.monotonic()
            wait = self._next_start - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_start = now + self._min_interval

    async def _get_json(self, url: str, params: dict | None = None) -> dict:
        self._bind_loop()
        assert self._semaphore is not None and self._client is not None
        for attempt in range(2):
            async with self._semaphore:
                await self._pace()
                try:
                    response = await self._client.get(url, params=params)
                except httpx.HTTPError as error:
                    raise NcbiError(f"NCBI request failed: {error}") from error

            if response.status_code in (429, 503) and attempt == 0:
                delay = _retry_after_seconds(response)
                logger.warning(
                    f"NCBI answered {response.status_code}; retrying in {delay:.1f}s."
                )
                await asyncio.sleep(delay)
                continue
            if response.status_code == 404:
                # Datasets answers an unknown taxon with an empty 200 today,
                # but has used 404 for it; either way it is "no data".
                return {}
            if response.status_code != 200:
                raise NcbiError(f"NCBI answered {response.status_code} for {url}")
            try:
                data = response.json()
            except ValueError as error:
                raise NcbiError(f"Unexpected NCBI response: {error}") from error
            if not isinstance(data, dict):
                raise NcbiError("Unexpected NCBI response: not an object")
            return data
        raise NcbiError("NCBI is rate limiting requests.")


def _retry_after_seconds(response: httpx.Response) -> float:
    value = response.headers.get("retry-after", "")
    try:
        seconds = float(value)
    except ValueError:
        seconds = 1.0
    return max(0.0, min(seconds, MAX_RETRY_AFTER_SECONDS))


_shared_client: NcbiClient | None = None


def get_ncbi_client() -> NcbiClient:
    """The process-wide client, so every request shares one rate limit."""
    global _shared_client
    if _shared_client is None:
        config = NcbiConfig()
        if not config.email:
            logger.warning(
                "NCBI_EMAIL is not set; NCBI asks E-utilities callers to "
                "identify themselves with a contact address."
            )
        if not config.api_key:
            logger.info(
                "NCBI_API_KEY is not set; NCBI requests are limited to 3 per second."
            )
        _shared_client = NcbiClient(config.api_key, config.email)
    return _shared_client
