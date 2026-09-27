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

from app.routers.species_data import get_literature_search, router
from app.services.col import ColBackboneService, ColTaxonSearch
from app.services.crossref import CrossrefClient
from app.services.literature import (
    MIN_SPECIES_RESULTS,
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
        client._learn_rate(response)
        assert client._min_interval == pytest.approx(0.2)


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
