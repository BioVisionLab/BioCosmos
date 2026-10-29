"""Tests for the species literature search.

The behaviours that matter: a species is searched under every name CoL knows
it by, a paper counts only if it actually names the taxon, the genus section
appears only when the species has too little literature of its own, and
CrossRef is called politely — identified, cached, and backed off.
"""

import asyncio
import os
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.configs.config import (
    DEFAULT_LITERATURE_WORK_TYPES,
    HigherTaxonLiteratureConfig,
    LiteratureConfig,
)
from app.routers.species_data import (
    get_higher_taxon_literature_search,
    get_literature_search,
    router,
)
from app.services.col import ColBackboneService, ColTaxonSearch
from app.services.crossref import CrossrefClient, CrossrefError
from app.services.literature import (
    MIN_SPECIES_RESULTS,
    HigherTaxonLiteraturePayload,
    HigherTaxonLiteratureSearch,
    LiteraturePayload,
    LiteratureSearch,
    congeners_mentioned,
    mentions_name,
    normalize_text,
    to_work,
)


@pytest.fixture
def taxon_search(memory_duckdb, col_fixture_dir):
    service = ColBackboneService.__new__(ColBackboneService)
    service.db_client = memory_duckdb
    service.path = os.path.join(col_fixture_dir, "NameUsage.tsv")
    service.vernacular_path = os.path.join(col_fixture_dir, "VernacularName.tsv")
    service.table = "col_taxonomy"
    service.vernacular_table = "col_vernacular"
    service.clade_rank = "order"
    service.clade_value = "Lepidoptera"
    service.skip_ingestion = False
    service._ingest_name_usage()
    service._ingest_vernacular_names()

    search = ColTaxonSearch.__new__(ColTaxonSearch)
    search.db_client = memory_duckdb
    search.table = "col_taxonomy"
    search.vernacular_table = "col_vernacular"
    search.matches_table = "col_taxonomy_matches"
    search._backbone_present = None
    return search


def work(doi: str, title: str, year: int = 2020, abstract: str | None = None) -> dict:
    item = {
        "DOI": doi,
        "title": [title],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "issued": {"date-parts": [[year, 1, 1]]},
        "container-title": ["J. Lepid. Soc."],
    }
    if abstract:
        item["abstract"] = abstract
    return item


class FakeCrossref:
    """A MockTransport that answers by `query.bibliographic` and logs calls."""

    def __init__(self, responses: dict[str, list[dict]]):
        self.responses = responses
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        query = parse_qs(urlparse(str(request.url)).query)["query.bibliographic"][0]
        items = self.responses.get(query, [])
        return httpx.Response(200, json={"status": "ok", "message": {"items": items}})

    def client(self, mailto: str | None = "test@example.org") -> CrossrefClient:
        client = CrossrefClient(mailto, transport=httpx.MockTransport(self.handler))
        client._min_interval = 0.0
        return client

    def queries(self) -> list[str]:
        return [
            parse_qs(urlparse(str(r.url)).query)["query.bibliographic"][0]
            for r in self.requests
        ]


# ---------------------------------------------------------------------------
# Name usages
# ---------------------------------------------------------------------------


class TestNameUsages:
    def test_lists_synonyms_and_congeners(self, taxon_search):
        usages = asyncio.run(taxon_search.name_usages("coenonympha_pamphilus"))
        assert usages["accepted_name"] == "Coenonympha pamphilus"
        assert usages["genus"] == "Coenonympha"
        assert [s["name"] for s in usages["synonyms"]] == ["Papilio pamphilus"]
        assert usages["synonyms"][0]["authorship"] == "Linnaeus, 1758"
        # The species itself is not its own congener; unranked usages are out.
        assert usages["congeners"] == ["Coenonympha dubia", "Coenonympha tullia"]

    def test_a_synonym_resolves_to_the_accepted_species(self, taxon_search):
        usages = asyncio.run(taxon_search.name_usages("Papilio pamphilus"))
        assert usages["accepted_name"] == "Coenonympha pamphilus"
        # Listed once, with CoL's authorship, not again as the recorded name.
        assert [s["status"] for s in usages["synonyms"]] == ["synonym"]

    def test_recombinations_rank_before_junior_synonyms(self, taxon_search):
        # Alphabetically "Aaa junior" would come first; a caller searching only
        # the first few names should get the recombinations instead.
        taxon_search.db_client.execute(
            """
            INSERT INTO col_taxonomy
                (usage_id, scientific_name, status, taxon_rank, accepted_id,
                 is_accepted)
            VALUES ('SYN2', 'Aaa junior', 'synonym', 'species', 'AAA1', false),
                   ('SYN3', 'Zzz pamphilus', 'synonym', 'species', 'AAA1', false)
            """
        )
        usages = asyncio.run(taxon_search.name_usages("coenonympha_pamphilus"))
        assert [s["name"] for s in usages["synonyms"]] == [
            "Papilio pamphilus",
            "Zzz pamphilus",
            "Aaa junior",
        ]

    def test_subgenus_is_dropped_from_names(self, taxon_search):
        usages = asyncio.run(taxon_search.name_usages("Zzzonympha tricolor"))
        assert usages["accepted_name"] == "Zzzonympha tricolor"
        assert usages["congeners"] == ["Zzzonympha pamphilus"]

    def test_unknown_name_returns_none(self, taxon_search):
        assert asyncio.run(taxon_search.name_usages("Nonexistent species")) is None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class TestMatching:
    def test_italics_split_across_tags(self):
        text = normalize_text("On <i>Danaus</i> <i>plexippus</i> migration")
        assert mentions_name(text, "Danaus plexippus")

    def test_double_escaped_markup(self):
        text = normalize_text(
            "Notes on &amp;lt;i&amp;gt;Danaus plexippus&amp;lt;/i&amp;gt;"
        )
        assert text == "Notes on Danaus plexippus"

    def test_subgenus_notation(self):
        text = normalize_text("Danaus (Danaus) plexippus in Spain")
        assert mentions_name(text, "Danaus plexippus")

    def test_abbreviated_genus_needs_the_full_genus_somewhere(self):
        assert mentions_name(
            "Danaus butterflies. D. plexippus migrates", "Danaus plexippus"
        )
        assert not mentions_name("D. plexippus migrates", "Danaus plexippus")

    def test_word_boundaries(self):
        assert not mentions_name("Danausx plexippus", "Danaus plexippus")
        assert not mentions_name("Danaus plexippusi", "Danaus plexippus")

    def test_case_insensitive_for_all_caps_titles(self):
        assert mentions_name("THE BIOLOGY OF DANAUS PLEXIPPUS", "Danaus plexippus")

    def test_congeners_mentioned(self):
        text = "Coenonympha tullia and C. dubia compared with Coenonympha arcania"
        found = congeners_mentioned(
            text, "Coenonympha", ["Coenonympha dubia", "Coenonympha tullia"]
        )
        assert found == ["Coenonympha dubia", "Coenonympha tullia"]

    def test_to_work_maps_fields(self):
        item = work("10.1/abc", "A  title\n with  space", 2019)
        item.update({"volume": "12", "issue": "3", "page": "1-9"})
        result = to_work(item)
        assert result.title == "A title with space"
        assert result.authors == ["Ada Lovelace"]
        assert result.published_year == 2019
        assert result.doi == "https://doi.org/10.1/abc"
        assert (result.volume, result.issue, result.pages) == ("12", "3", "1-9")

    def test_to_work_names_a_book_chapter_by_its_publisher(self):
        item = work("10.1/ch", "Coenonympha in the Alps")
        item.update({"type": "book-chapter", "publisher": "Springer"})
        del item["container-title"]
        assert to_work(item).journal == "Springer"

    def test_to_work_keeps_the_type_and_names_a_dataset_by_its_publisher(self):
        item = work("10.1/data", "Coenonympha pamphilus wing images")
        item.update({"type": "dataset", "publisher": "Dryad"})
        del item["container-title"]
        result = to_work(item)
        assert result.publication_type == "dataset"
        assert result.journal == "Dryad"
        assert result.model_dump(by_alias=True)["publicationType"] == "dataset"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def species_papers(n: int) -> list[dict]:
    return [
        work(f"10.1/cp{i}", f"Coenonympha pamphilus study {i}", 2000 + i)
        for i in range(n)
    ]


class TestLiteratureSearch:
    def test_searches_accepted_name_and_synonyms(self, taxon_search):
        fake = FakeCrossref(
            {
                "Coenonympha pamphilus": species_papers(MIN_SPECIES_RESULTS),
                "Papilio pamphilus": [
                    work("10.1/old", "Papilio pamphilus in 1998", 1998)
                ],
            }
        )
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search(
                "coenonympha_pamphilus"
            )
        )
        assert payload is not None
        assert set(fake.queries()) == {"Coenonympha pamphilus", "Papilio pamphilus"}
        assert payload.synonyms_searched == ["Papilio pamphilus"]
        old = next(w for w in payload.species if (w.doi or "").endswith("10.1/old"))
        assert (old.matched_via, old.matched_name) == ("synonym", "Papilio pamphilus")
        # Enough species papers: no genus search at all.
        assert payload.genus_related is None
        assert "Coenonympha Nymphalidae" not in fake.queries()

    def test_irrelevant_hits_are_dropped(self, taxon_search):
        fake = FakeCrossref(
            {"Coenonympha pamphilus": [work("10.1/x", "A study of Maniola jurtina")]}
        )
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search(
                "coenonympha_pamphilus"
            )
        )
        assert payload is not None
        assert payload.species == []

    def test_abstract_mentions_count(self, taxon_search):
        fake = FakeCrossref(
            {
                "Coenonympha pamphilus": [
                    work(
                        "10.1/a",
                        "Heath butterflies",
                        abstract="<jats:p>We studied <i>Coenonympha pamphilus</i>.</jats:p>",
                    )
                ]
            }
        )
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search(
                "coenonympha_pamphilus"
            )
        )
        assert payload is not None
        assert [w.doi for w in payload.species] == ["https://doi.org/10.1/a"]

    def test_genus_tier_runs_when_species_results_are_few(self, taxon_search):
        fake = FakeCrossref(
            {
                "Coenonympha pamphilus": species_papers(2),
                "Coenonympha Nymphalidae": [
                    # Already in the species tier: not repeated below.
                    work("10.1/cp0", "Coenonympha pamphilus study 0"),
                    # Names the species itself: promoted to the species tier.
                    work("10.1/promoted", "Coenonympha pamphilus and relatives"),
                    work("10.1/tullia", "Coenonympha tullia in bogs", 2021),
                    work("10.1/genus", "A revision of Coenonympha", 2015),
                    # Another genus entirely: excluded.
                    work("10.1/noise", "Maniola jurtina ecology"),
                ],
            }
        )
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search(
                "coenonympha_pamphilus"
            )
        )
        assert payload is not None
        species_dois = {(w.doi or "").rsplit("/", 1)[-1] for w in payload.species}
        assert species_dois == {"cp0", "cp1", "promoted"}
        genus = payload.genus_related
        assert genus is not None
        assert [(w.doi or "").rsplit("/", 1)[-1] for w in genus] == ["tullia", "genus"]
        assert genus[0].mentions == ["Coenonympha tullia"]
        assert genus[1].mentions == []

    def test_species_sorted_newest_first(self, taxon_search):
        fake = FakeCrossref({"Coenonympha pamphilus": species_papers(12)})
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search(
                "coenonympha_pamphilus"
            )
        )
        assert payload is not None
        years = [
            w.published_year for w in payload.species if w.published_year is not None
        ]
        assert len(years) == len(payload.species)
        assert years == sorted(years, reverse=True)

    def test_name_outside_backbone_is_still_searched(self, taxon_search):
        fake = FakeCrossref({"Fooia barus": [work("10.1/f", "Fooia barus found")]})
        payload = asyncio.run(
            LiteratureSearch(taxon_search, fake.client()).search("fooia_barus")
        )
        assert payload is not None
        assert payload.accepted_name == "Fooia barus"
        assert len(payload.species) == 1

    def test_a_crossref_failure_makes_the_result_partial(self, taxon_search):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = CrossrefClient("t@example.org", transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        payload = asyncio.run(
            LiteratureSearch(taxon_search, client).search("coenonympha_pamphilus")
        )
        assert payload is not None
        assert payload.partial is True
        assert payload.species == []


# ---------------------------------------------------------------------------
# CrossRef etiquette
# ---------------------------------------------------------------------------


class TestCrossrefClient:
    def test_identifies_itself_for_the_polite_pool(self):
        fake = FakeCrossref({})
        asyncio.run(fake.client("me@example.org").search_works("Danaus plexippus"))
        request = fake.requests[0]
        params = parse_qs(urlparse(str(request.url)).query)
        assert params["mailto"] == ["me@example.org"]
        assert "mailto:me@example.org" in request.headers["User-Agent"]
        assert "abstract" in params["select"][0]
        assert "has-abstract" not in params["filter"][0]
        filters = params["filter"][0].split(",")
        assert {"type:journal-article", "type:dataset"} <= set(filters)
        assert "type" in params["select"][0].split(",")

    def test_without_mailto_starts_at_the_public_rate(self):
        assert CrossrefClient(None)._min_interval == pytest.approx(1.0)
        assert CrossrefClient("t@example.org")._min_interval == pytest.approx(1 / 3)

    def test_without_mailto_uses_one_connection(self):
        client = FakeCrossref({}).client(mailto=None)
        assert client._concurrency == 1
        assert "mailto" not in client.build_url("x", 1)

    def test_caches_and_shares_in_flight_requests(self):
        fake = FakeCrossref({"Danaus plexippus": [work("10.1/a", "Danaus plexippus")]})
        client = fake.client()

        async def run():
            first, second = await asyncio.gather(
                client.search_works("Danaus plexippus"),
                client.search_works("Danaus plexippus"),
            )
            third = await client.search_works("Danaus plexippus")
            return first, second, third

        first, second, third = asyncio.run(run())
        assert first == second == third
        assert len(fake.requests) == 1

    def test_backs_off_once_on_429(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"message": {"items": []}})

        client = CrossrefClient("t@example.org", transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        assert asyncio.run(client.search_works("x")) == []
        assert len(calls) == 2

    def test_gives_up_after_a_second_429(self):
        from app.services.crossref import CrossrefError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        client = CrossrefClient("t@example.org", transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        with pytest.raises(CrossrefError):
            asyncio.run(client.search_works("x"))

    def test_learns_the_advertised_rate(self):
        client = CrossrefClient("t@example.org")
        response = httpx.Response(
            200, headers={"x-rate-limit-limit": "5", "x-rate-limit-interval": "1s"}
        )
        client._learn_limits(response)
        assert client._min_interval == pytest.approx(0.2)

    def test_lowers_concurrency_to_the_advertised_limit(self):
        client = CrossrefClient("t@example.org")
        client._learn_limits(httpx.Response(200, headers={"x-concurrency-limit": "1"}))
        assert client._concurrency == 1
        # A higher advertised limit never raises the cap past the pool's.
        client._learn_limits(httpx.Response(200, headers={"x-concurrency-limit": "9"}))
        assert client._concurrency == 1

    def test_filter_searches_every_type_and_every_year_by_default(self):
        client = CrossrefClient("t@example.org")
        params = parse_qs(urlparse(client.build_url("Danaus plexippus", 10)).query)
        filters = params["filter"][0].split(",")
        assert filters == [f"type:{t}" for t in DEFAULT_LITERATURE_WORK_TYPES]
        assert "cursor" not in params

    def test_from_year_adds_a_floor(self):
        client = CrossrefClient("t@example.org", from_year=1900)
        params = parse_qs(urlparse(client.build_url("Danaus plexippus", 10)).query)
        assert "from-pub-date:1900-01-01" in params["filter"][0].split(",")

    def test_a_403_pauses_every_request(self):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)

            return httpx.Response(403)

        client = CrossrefClient("t@example.org", transport=httpx.MockTransport(handler))
        client._min_interval = 0.0

        with pytest.raises(CrossrefError):
            asyncio.run(client.search_works("Danaus plexippus"))

        with pytest.raises(CrossrefError):
            asyncio.run(client.search_works("Danaus chrysippus"))

        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Paging
# ---------------------------------------------------------------------------


def literature_config(**overrides) -> LiteratureConfig:
    config = LiteratureConfig.__new__(LiteratureConfig)
    config._literature_config = {
        "accepted_rows": 4,
        "max_accepted_pages": 2,
        **overrides,
    }

    return config


class PagedCrossref:
    """Answers the accepted-name query page by page, by cursor."""

    def __init__(self, pages: dict[str, tuple[list[dict], str | None]]):
        self.pages = pages
        self.cursors: list[str | None] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        query = params["query.bibliographic"][0]

        if query != "Coenonympha pamphilus":
            return httpx.Response(200, json={"message": {"items": []}})

        cursor = params.get("cursor", [None])[0]
        self.cursors.append(cursor)
        items, next_cursor = self.pages.get(cursor or "", ([], None))

        return httpx.Response(
            200, json={"message": {"items": items, "next-cursor": next_cursor}}
        )

    def search(self, taxon_search: ColTaxonSearch) -> LiteraturePayload | None:
        client = CrossrefClient(
            "t@example.org", transport=httpx.MockTransport(self.handler)
        )
        client._min_interval = 0.0
        search = LiteratureSearch(taxon_search, client, literature_config())

        return asyncio.run(search.search("coenonympha_pamphilus"))


class TestAcceptedNamePaging:
    def test_a_full_relevant_page_fetches_the_next(self, taxon_search):
        fake = PagedCrossref(
            {
                "*": (species_papers(4), "next-1"),
                "next-1": (
                    [work("10.1/more", "Coenonympha pamphilus again")],
                    "next-2",
                ),
            }
        )
        payload = fake.search(taxon_search)
        assert fake.cursors == ["*", "next-1"]
        assert payload is not None
        assert any((w.doi or "").endswith("10.1/more") for w in payload.species)

    def test_a_mostly_irrelevant_page_stops_paging(self, taxon_search):
        noise = [work(f"10.1/n{i}", f"Maniola jurtina {i}") for i in range(4)]
        fake = PagedCrossref({"*": (noise, "next-1")})
        fake.search(taxon_search)
        assert fake.cursors == ["*"]

    def test_a_short_page_is_the_last(self, taxon_search):
        fake = PagedCrossref({"*": (species_papers(3), "next-1")})
        fake.search(taxon_search)
        assert fake.cursors == ["*"]

    def test_payload_reports_the_year_floor(self, taxon_search):
        client = FakeCrossref({}).client()
        client.from_year = 1950
        payload = asyncio.run(
            LiteratureSearch(taxon_search, client).search("coenonympha_pamphilus")
        )
        assert payload is not None
        assert payload.from_year == 1950


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class StubSearch:
    def __init__(self, payload):
        self.payload = payload

    async def search(self, name):
        return self.payload


def router_client(payload) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_literature_search] = lambda: StubSearch(payload)
    return TestClient(app)


class TestLiteratureRouter:
    def test_complete_result_is_cached_for_a_day(self):
        payload = LiteraturePayload(accepted_name="Danaus plexippus", genus="Danaus")
        response = router_client(payload).get("/species/danaus_plexippus/literature")
        assert response.status_code == 200
        assert "max-age=86400" in response.headers["Cache-Control"]
        body = response.json()
        assert body["acceptedName"] == "Danaus plexippus"
        assert body["genusRelated"] is None
        assert body["minSpeciesResults"] == MIN_SPECIES_RESULTS

    def test_partial_result_is_cached_briefly(self):
        payload = LiteraturePayload(accepted_name="Danaus plexippus", partial=True)
        response = router_client(payload).get("/species/danaus_plexippus/literature")
        assert response.status_code == 200
        assert "max-age=300" in response.headers["Cache-Control"]

    def test_non_species_returns_404(self):
        response = router_client(None).get("/species/danaus/literature")
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"


# ---------------------------------------------------------------------------
# Higher taxa
# ---------------------------------------------------------------------------


class FailingCrossref:
    """Fails every request after the first `ok` with a server error."""

    def __init__(self, ok: int, items: list[dict]):
        self.ok = ok
        self.items = items
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1

        if self.calls > self.ok:
            return httpx.Response(400, json={"message": "bad"})

        return httpx.Response(
            200, json={"message": {"items": self.items, "next-cursor": "next"}}
        )


def higher_taxon_config(**overrides) -> HigherTaxonLiteratureConfig:
    config = HigherTaxonLiteratureConfig.__new__(HigherTaxonLiteratureConfig)
    config._config = {"rows": 4, "max_pages": 5, "min_paging_yield": 0.3, **overrides}

    return config


def higher_taxon_search(handler, **config) -> HigherTaxonLiteratureSearch:
    client = CrossrefClient("t@example.org", transport=httpx.MockTransport(handler))
    client._min_interval = 0.0

    return HigherTaxonLiteratureSearch(client, higher_taxon_config(**config))


class PagedQuery:
    """Answers one query page by page, by cursor, and logs the cursors."""

    def __init__(self, pages: dict[str, tuple[list[dict], str | None]]):
        self.pages = pages
        self.cursors: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        cursor = parse_qs(urlparse(str(request.url)).query).get("cursor", ["*"])[0]
        self.cursors.append(cursor)
        items, next_cursor = self.pages.get(cursor, ([], None))

        return httpx.Response(
            200, json={"message": {"items": items, "next-cursor": next_cursor}}
        )


class TestHigherTaxonLiterature:
    def test_keeps_only_works_naming_the_taxon(self):
        fake = FakeCrossref(
            {
                "Nymphalidae": [
                    work("10.1/a", "Phylogeny of Nymphalidae", 2015),
                    work("10.1/b", "A butterfly survey", 2021),
                    work(
                        "10.1/c",
                        "Wing patterns",
                        2023,
                        abstract="<jats:p>Across the Nymphalidae ...</jats:p>",
                    ),
                ]
            }
        )
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search("family", "nymphalidae")
        )
        assert payload is not None
        assert fake.queries() == ["Nymphalidae"]
        assert payload.name == "Nymphalidae"
        assert payload.rank == "family"
        # Newest first, and the survey that never names the family is dropped.
        assert [w.doi for w in payload.works] == [
            "https://doi.org/10.1/c",
            "https://doi.org/10.1/a",
        ]
        assert payload.partial is False

    def test_a_lower_case_word_is_not_the_genus(self):
        fake = FakeCrossref(
            {
                "Morpho": [
                    work("10.1/a", "Structural color in Morpho butterflies"),
                    work("10.1/b", "Leaf morpho types and morpho-space"),
                ]
            }
        )
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search("genus", "morpho")
        )
        assert payload is not None
        assert [w.doi for w in payload.works] == ["https://doi.org/10.1/a"]

    def test_a_hyphenated_compound_is_not_the_genus(self):
        fake = FakeCrossref(
            {
                "Morpho": [
                    work("10.1/a", "Blue Morpho wing scales"),
                    work("10.1/b", "The Historical Morpho-Syntax of Chinese"),
                    work("10.1/c", "Morpho-Anatomical Traits of Colchicum"),
                ]
            }
        )
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search("genus", "morpho")
        )
        assert payload is not None
        assert [w.doi for w in payload.works] == ["https://doi.org/10.1/a"]

    def test_a_genus_is_searched_beside_its_family(self):
        fake = FakeCrossref(
            {
                "Morpho Nymphalidae": [
                    work("10.1/a", "Morpho butterflies of Peru"),
                    work("10.1/b", "A Nymphalidae checklist"),
                ]
            }
        )
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search(
                "genus", "morpho", "nymphalidae"
            )
        )
        assert payload is not None
        assert fake.queries() == ["Morpho Nymphalidae"]
        assert payload.context == "Nymphalidae"
        # Only the genus has to appear; the family alone does not keep a work.
        assert [w.doi for w in payload.works] == ["https://doi.org/10.1/a"]

    def test_a_family_context_is_ignored_above_genus(self):
        fake = FakeCrossref({})
        search = HigherTaxonLiteratureSearch(fake.client())
        payload = asyncio.run(search.search("family", "nymphalidae", "papilionidae"))
        assert payload is not None
        assert fake.queries() == ["Nymphalidae"]
        assert payload.context is None

    def test_a_family_given_in_parentheses_counts_as_named(self):
        """The usual form: "(Lepidoptera: Nymphalidae)" after a binomial.

        The species search drops parentheticals to strip a subgenus; this
        search must not, or it loses most of what it finds.
        """
        fake = FakeCrossref(
            {
                "Nymphalidae": [
                    work(
                        "10.1/a",
                        "Biology of Issoria lathonia (Lepidoptera: Nymphalidae)",
                    ),
                    work(
                        "10.1/b",
                        "Wing scales",
                        abstract="<jats:p>In Morpho (Nymphalidae), ...</jats:p>",
                    ),
                ]
            }
        )
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search("family", "nymphalidae")
        )
        assert payload is not None
        assert len(payload.works) == 2

    def test_a_family_name_in_capitals_is_kept(self):
        fake = FakeCrossref({"Nymphalidae": [work("10.1/a", "NYMPHALIDAE")]})
        payload = asyncio.run(
            HigherTaxonLiteratureSearch(fake.client()).search("family", "nymphalidae")
        )
        assert payload is not None
        assert len(payload.works) == 1

    def test_pages_on_past_the_species_limit_while_the_yield_holds(self):
        def page(prefix: str, relevant: int) -> list[dict]:
            return [
                work(f"10.1/{prefix}{i}", "Nymphalidae" if i < relevant else "Other")
                for i in range(4)
            ]

        fake = PagedQuery(
            {
                "*": (page("a", 2), "c2"),
                "c2": (page("b", 2), "c3"),
                "c3": (page("c", 2), "c4"),
                # One in four is below the 0.3 floor: the last page fetched.
                "c4": (page("d", 1), "c5"),
                "c5": (page("e", 4), None),
            }
        )
        payload = asyncio.run(
            higher_taxon_search(fake.handler).search("family", "nymphalidae")
        )
        assert fake.cursors == ["*", "c2", "c3", "c4"]
        assert payload is not None
        assert len(payload.works) == 7

    def test_max_pages_caps_the_requests(self):
        pages: dict[str, tuple[list[dict], str | None]] = {
            "*" if i == 0 else f"c{i}": (
                [work(f"10.1/{i}-{j}", "Nymphalidae") for j in range(4)],
                f"c{i + 1}",
            )
            for i in range(10)
        }
        fake = PagedQuery(pages)
        asyncio.run(
            higher_taxon_search(fake.handler, max_pages=3).search(
                "family", "nymphalidae"
            )
        )
        assert len(fake.cursors) == 3

    def test_a_malformed_name_is_refused_without_a_request(self):
        fake = FakeCrossref({})
        search = HigherTaxonLiteratureSearch(fake.client())
        assert asyncio.run(search.search("family", "nymphalidae; drop")) is None
        assert asyncio.run(search.search("genus", "danaus plexippus")) is None
        assert asyncio.run(search.search("genus", "not-a-name")) is None
        assert fake.requests == []

    def test_a_later_page_failing_keeps_the_first_and_flags_partial(self):
        papers = [work(f"10.1/p{i}", f"Nymphalidae study {i}") for i in range(4)]
        fake = FailingCrossref(ok=1, items=papers)
        payload = asyncio.run(
            higher_taxon_search(fake.handler).search("family", "nymphalidae")
        )
        assert payload is not None
        assert fake.calls == 2
        assert len(payload.works) == 4
        assert payload.partial is True

    def test_the_first_page_failing_is_an_empty_partial_list(self):
        fake = FailingCrossref(ok=0, items=[])
        payload = asyncio.run(
            higher_taxon_search(fake.handler).search("order", "lepidoptera")
        )
        assert payload is not None
        assert payload.works == []
        assert payload.partial is True


class StubHigherTaxonSearch:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, str, str | None]] = []

    async def search(self, rank, name, family=None):
        self.calls.append((rank, name, family))

        return self.payload

    def provide(self) -> "StubHigherTaxonSearch":
        return self


def higher_taxon_router_client(stub: StubHigherTaxonSearch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_higher_taxon_literature_search] = stub.provide

    return TestClient(app)


class TestHigherTaxonLiteratureRouter:
    @pytest.mark.parametrize("rank", ["order", "family", "genus"])
    def test_each_rank_route_passes_its_rank(self, rank):
        stub = StubHigherTaxonSearch(
            HigherTaxonLiteraturePayload(name="Danaus", rank=rank)
        )
        response = higher_taxon_router_client(stub).get(f"/{rank}/danaus/literature")
        assert response.status_code == 200
        assert stub.calls == [(rank, "danaus", None)]
        assert "max-age=86400" in response.headers["Cache-Control"]
        assert response.json()["works"] == []

    def test_the_genus_route_passes_its_family(self):
        stub = StubHigherTaxonSearch(
            HigherTaxonLiteraturePayload(name="Danaus", rank="genus")
        )
        higher_taxon_router_client(stub).get(
            "/genus/danaus/literature?family=Nymphalidae"
        )
        assert stub.calls == [("genus", "danaus", "Nymphalidae")]

    def test_partial_result_is_cached_briefly(self):
        stub = StubHigherTaxonSearch(
            HigherTaxonLiteraturePayload(name="Danaus", rank="genus", partial=True)
        )
        response = higher_taxon_router_client(stub).get("/genus/danaus/literature")
        assert "max-age=300" in response.headers["Cache-Control"]
        assert response.json()["fromYear"] is None

    def test_a_malformed_name_returns_404(self):
        response = higher_taxon_router_client(StubHigherTaxonSearch(None)).get(
            "/family/not-a-name/literature"
        )
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"
