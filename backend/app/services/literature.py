"""Literature search for a species, using every name it has been published under.

Searching CrossRef for the accepted name alone found nothing for many species:
papers written before a genus transfer use the old combination, and a species
with little literature of its own left the tab empty. This searches the
accepted name and its Catalogue of Life synonyms, and when that still finds
fewer than ``MIN_SPECIES_RESULTS`` papers, adds a separate, clearly labelled
set of papers on the genus. The work types, the year floor and the per-query
depth come from the ``literature`` section of config.yaml.

CrossRef's relevance ranking is fuzzy, so every hit is kept only if its title
or abstract actually names the taxon. Names are matched after normalizing
the markup CrossRef titles carry (``<i>Danaus</i> <i>plexippus</i>``), with
the subgenus notation stripped (``Danaus (Danaus) plexippus``), and with the
abbreviated form abstracts use (``D. plexippus``).
"""

import asyncio
import html
import logging
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..configs.config import LiteratureConfig
from .col import ColTaxonSearch
from .crossref import CrossrefClient, CrossrefError

logger = logging.getLogger(__name__)

# Below this many species-level papers, the genus-level section is added.
MIN_SPECIES_RESULTS = 10
MAX_GENUS_RESULTS = 30
# The accepted name's next page is fetched only when this share of a full page
# named the species: relevant results are then likely to continue.
MIN_PAGING_YIELD = 0.5

_TAG = re.compile(r"<[^>]+>")
_PARENTHETICAL = re.compile(r"\([^)]*\)")
_WHITESPACE = re.compile(r"\s+")


class LiteratureWork(BaseModel):
    """One publication, in the shape the literature list renders."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str
    # The CrossRef work type, e.g. "journal-article" or "dataset".
    publication_type: str | None = None
    authors: list[str]
    published_year: int | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    # Species tier: the name the paper was found under.
    matched_name: str | None = None
    matched_via: Literal["accepted", "synonym"] | None = None
    # Genus tier: the other species of the genus the paper names.
    mentions: list[str] = []


class LiteraturePayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    accepted_name: str
    genus: str | None = None
    family: str | None = None
    synonyms_searched: list[str] = []
    species: list[LiteratureWork] = []
    # None when the genus search was not needed; a list (maybe empty) when it ran.
    genus_related: list[LiteratureWork] | None = None
    min_species_results: int = MIN_SPECIES_RESULTS
    # True when a CrossRef request failed, so the lists may be incomplete.
    partial: bool = False
    # The earliest publication year searched; None when every year is.
    from_year: int | None = None


def unescape_fully(value: str) -> str:
    """Undo HTML escaping, including the double escaping some publishers
    deposit (``&amp;lt;i&amp;gt;``), and collapse whitespace."""
    for _ in range(3):
        unescaped = html.unescape(value)
        if unescaped == value:
            break
        value = unescaped
    return _WHITESPACE.sub(" ", value).strip()


def normalize_text(value: str | None) -> str:
    """Plain text from a CrossRef title or JATS abstract, for name matching."""
    if not value:
        return ""
    text = _TAG.sub(" ", unescape_fully(value))
    text = _PARENTHETICAL.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def _binomial_pattern(genus: str, epithets: list[str]) -> re.Pattern:
    """Match `Genus epithet` or `G. epithet` for any of the given epithets."""
    alternatives = "|".join(re.escape(e) for e in epithets)
    return re.compile(
        rf"\b(?:{re.escape(genus)}|{re.escape(genus[0])}\.)\s+({alternatives})\b",
        re.IGNORECASE,
    )


def _genus_pattern(genus: str) -> re.Pattern:
    # Case-sensitive: a lower-case word that happens to share the spelling
    # ("morpho-" against Morpho) is not the genus.
    return re.compile(rf"\b{re.escape(genus)}\b")


def mentions_name(text: str, name: str) -> bool:
    """Whether normalized ``text`` names the binomial ``name``.

    The abbreviated genus counts only when the full genus also appears, which
    is how an abstract introduces a name before shortening it; on its own
    ``C. pamphilus`` could belong to any genus starting with C.
    """
    parts = name.split()
    if len(parts) != 2:
        return False
    genus, epithet = parts
    match = _binomial_pattern(genus, [epithet]).search(text)
    if not match:
        return False
    if match.group(0).lower().startswith(genus.lower()):
        return True
    return re.search(rf"\b{re.escape(genus)}\b", text, re.IGNORECASE) is not None


def congeners_mentioned(text: str, genus: str, congeners: list[str]) -> list[str]:
    """The congeners a genus-level paper names, using one combined pattern."""
    epithets = {
        name.split()[1].lower(): name
        for name in congeners
        if len(name.split()) == 2 and name.split()[0].lower() == genus.lower()
    }
    if not epithets:
        return []
    found = {
        epithets[match.group(1).lower()]
        for match in _binomial_pattern(genus, list(epithets)).finditer(text)
        if match.group(1).lower() in epithets
    }
    return sorted(found)


def _first(value) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _year(item: dict) -> int | None:
    for key in ("issued", "published-print", "published-online"):
        try:
            year = item[key]["date-parts"][0][0]
        except (KeyError, IndexError, TypeError):
            continue
        if year is not None:
            try:
                return int(year)
            except (TypeError, ValueError):
                continue
    return None


def _doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    if doi.startswith(("http://", "https://")):
        return doi
    return f"https://doi.org/{doi}"


def to_work(item: dict) -> LiteratureWork:
    """Map a CrossRef record to the rendered fields.

    Escaping and stray whitespace are undone here, but casing is not: the
    frontend owns how titles and author names are displayed.
    """
    authors = [
        " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name", "")
        for a in item.get("author") or []
    ]
    title = _first(item.get("title"))
    publication_type = _first(item.get("type"))
    journal = _first(item.get("container-title"))

    # Books, reports, theses and datasets often have no container title.
    if journal is None and publication_type != "journal-article":
        journal = _first(item.get("publisher"))

    return LiteratureWork(
        # Markup such as <i> is kept for the frontend to render as italics.
        title=unescape_fully(title) if title else "No title available",
        publication_type=publication_type,
        authors=[a for a in authors if a],
        published_year=_year(item),
        journal=unescape_fully(journal) if journal else None,
        volume=_first(item.get("volume")),
        issue=_first(item.get("issue")),
        pages=_first(item.get("page")),
        doi=_doi_url(item.get("DOI")),
    )


def _work_key(item: dict) -> str:
    doi = item.get("DOI")
    if doi:
        return doi.lower()
    return normalize_text(_first(item.get("title"))).lower()


def _searchable_text(item: dict) -> str:
    return f"{normalize_text(_first(item.get('title')))} {normalize_text(item.get('abstract'))}"


def _sort_newest_first(works: list[LiteratureWork]) -> list[LiteratureWork]:
    # Stable, so CrossRef's relevance order survives within a year.
    return sorted(works, key=lambda w: -(w.published_year or 0))


def _crossref_failed(result: object, accepted: str) -> bool:
    """Whether a gathered CrossRef result failed. A CrossRef error only makes
    the search partial; anything else is a bug and is raised."""
    if not isinstance(result, BaseException):
        return False

    if not isinstance(result, CrossrefError):
        raise result

    logger.warning(f"Literature search incomplete for {accepted}: {result}")

    return True


def _slug_to_name(query: str) -> str:
    parts = query.replace("_", " ").split()
    if not parts:
        return ""
    return " ".join([parts[0].capitalize(), *(p.lower() for p in parts[1:])])


class LiteratureSearch:
    """Find publications on a species, its synonyms, and, if few, its genus."""

    def __init__(
        self,
        taxon_search: ColTaxonSearch,
        crossref: CrossrefClient,
        config: LiteratureConfig | None = None,
    ):
        self.taxon_search = taxon_search
        self.crossref = crossref
        self.config = config or LiteratureConfig()

    async def _accepted_items(
        self, accepted: str, names: list[str]
    ) -> tuple[list[dict], bool]:
        """The accepted name's results, paging on while pages come back full
        and mostly relevant. Returns the items and whether a later page failed.
        """
        rows = self.config.accepted_rows
        items: list[dict] = []
        cursor = "*"

        for page_number in range(self.config.max_accepted_pages):
            try:
                page, next_cursor = await self.crossref.search_works_page(
                    accepted, rows, cursor
                )
            except CrossrefError:
                # The first page failing fails the query; a later one only
                # leaves it short.
                if page_number == 0:
                    raise

                logger.warning(f"Later literature page failed for {accepted}.")

                return items, True

            items.extend(page)
            relevant = sum(
                1
                for item in page
                if any(mentions_name(_searchable_text(item), n) for n in names)
            )

            if len(page) < rows or not next_cursor:
                break

            if relevant < MIN_PAGING_YIELD * len(page):
                break

            cursor = next_cursor

        return items, False

    async def search(self, query: str) -> LiteraturePayload | None:
        usages = await self.taxon_search.name_usages(query)
        if usages is None:
            # Not in the backbone: still worth searching the name as given.
            name = _slug_to_name(query)
            if name.count(" ") < 1:
                return None
            usages = {
                "accepted_name": name,
                "genus": name.split()[0],
                "family": None,
                "synonyms": [],
                "congeners": [],
            }

        accepted = usages["accepted_name"]
        genus = usages["genus"]
        synonyms = [s["name"] for s in usages["synonyms"]][
            : self.config.max_synonym_queries
        ]
        # Accepted first, so a paper naming both is credited to the accepted name.
        names = [accepted, *synonyms]

        accepted_result, *synonym_results = await asyncio.gather(
            self._accepted_items(accepted, names),
            *(
                self.crossref.search_works(s, self.config.synonym_rows)
                for s in synonyms
            ),
            return_exceptions=True,
        )
        partial = False
        species: dict[str, LiteratureWork] = {}

        if _crossref_failed(accepted_result, accepted):
            partial = True
        elif isinstance(accepted_result, tuple):
            items, incomplete = accepted_result
            partial = incomplete
            self._collect_species(items, names, accepted, species)

        for result in synonym_results:
            if _crossref_failed(result, accepted):
                partial = True
                continue

            if isinstance(result, list):
                self._collect_species(result, names, accepted, species)

        payload = LiteraturePayload(
            accepted_name=accepted,
            genus=genus,
            family=usages.get("family"),
            synonyms_searched=synonyms,
            partial=partial,
            from_year=self.crossref.from_year,
        )

        if len(species) < MIN_SPECIES_RESULTS and genus:
            genus_query = " ".join(p for p in (genus, usages.get("family")) if p)
            try:
                items = await self.crossref.search_works(
                    genus_query, self.config.genus_rows
                )
            except CrossrefError as error:
                logger.warning(f"Genus literature search failed for {genus}: {error}")
                payload.partial = True
                items = None
            if items is not None:
                # The genus search can surface papers on the species itself
                # that the name searches ranked too low; those belong above.
                self._collect_species(items, names, accepted, species)
                payload.genus_related = self._collect_genus(
                    items, genus, usages["congeners"], species
                )

        payload.species = _sort_newest_first(list(species.values()))
        return payload

    @staticmethod
    def _collect_species(
        items: list[dict],
        names: list[str],
        accepted: str,
        into: dict[str, LiteratureWork],
    ) -> None:
        for item in items:
            key = _work_key(item)
            if not key or key in into:
                continue
            text = _searchable_text(item)
            matched = next((n for n in names if mentions_name(text, n)), None)
            if matched is None:
                continue
            work = to_work(item)
            work.matched_name = matched
            work.matched_via = "accepted" if matched == accepted else "synonym"
            into[key] = work

    @staticmethod
    def _collect_genus(
        items: list[dict],
        genus: str,
        congeners: list[str],
        species: dict[str, LiteratureWork],
    ) -> list[LiteratureWork]:
        pattern = _genus_pattern(genus)
        seen: set[str] = set()
        works: list[LiteratureWork] = []
        for item in items:
            key = _work_key(item)
            if not key or key in species or key in seen:
                continue
            text = _searchable_text(item)
            if not pattern.search(text):
                continue
            seen.add(key)
            work = to_work(item)
            work.mentions = congeners_mentioned(text, genus, congeners)
            works.append(work)
            if len(works) >= MAX_GENUS_RESULTS:
                break
        return _sort_newest_first(works)
