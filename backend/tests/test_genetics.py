"""Tests for the species genetics summary.

The behaviours that matter: mitochondrial data is reported even for a species
without an annotated genome, the species' own reference mitogenome wins over
a subspecies', a failed or slow NCBI call makes the result partial rather
than failing it, and NCBI is called politely: identified, paced, cached,
backed off, and never asked for more than the page needs.
"""

import asyncio
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.species_data import get_genetics_summary, router
from app.services.genetics import (
    MITOCHONDRIAL_MARKERS,
    GeneticsBusy,
    GeneticsPayload,
    GeneticsSummary,
    Mitochondrion,
    choose_assembly,
    choose_reference,
    normalize_species_name,
    organism_query,
    to_assembly,
)
from app.services.ncbi import (
    MIN_INTERVAL_WITH_KEY,
    MIN_INTERVAL_WITHOUT_KEY,
    NcbiClient,
    NcbiError,
)


def mito_report(organism: str, refseq: str = "NC_000001.1") -> dict:
    return {
        "description": "Mitochondrion",
        "refseq": {"accession": refseq, "submission_date": "2015-11-05"},
        "genbank": {"accession": "KP000001.1", "submission_date": "2014-11-25"},
        "organism": {"organism_name": organism},
        "length": 17044,
        "topology": "Circular",
        "gene_count": 37,
    }


def genome_report(
    organism: str,
    accession: str = "GCF_018135715.1",
    *,
    level: str = "Chromosome",
    contig_n50: int = 3940764,
    reference: bool = False,
    annotated: bool = False,
    release_date: str = "2021-04-26",
) -> dict:
    report = {
        "accession": accession,
        "paired_accession": "GCA_018135715.1",
        "organism": {"organism_name": organism},
        "assembly_info": {
            "assembly_name": "MEX_DaPlex",
            "assembly_level": level,
            "release_date": release_date,
            "submitter": "Langebio / CINVESTAV",
            "sequencing_tech": "PacBio Sequel",
            **({"refseq_category": "reference genome"} if reference else {}),
        },
        "assembly_stats": {
            "total_number_of_chromosomes": 30,
            "total_sequence_length": "245173502",
            "number_of_contigs": 108,
            "contig_n50": contig_n50,
            "number_of_scaffolds": 66,
            "scaffold_n50": 8158176,
            "gc_percent": 32,
            "genome_coverage": "448",
        },
    }
    if annotated:
        report["annotation_info"] = {
            "name": "GCF_018135715.1-RS_2023_11",
            "provider": "NCBI RefSeq",
            "release_date": "2023-11-16",
            "stats": {"gene_counts": {"total": 14790, "protein_coding": 12804}},
            "busco": {"busco_lineage": "lepidoptera_odb10", "complete": 0.9947},
        }
    return report


class FakeNcbi:
    """A MockTransport answering Datasets and esearch, logging every call.

    `counts` maps a substring of the esearch term to its count; the first
    match wins, so put the more specific substrings first.
    """

    def __init__(
        self,
        gene_counts: dict[str, int] | None = None,
        reports: list[dict] | None = None,
        counts: dict[str, int] | None = None,
        fail: str | None = None,
        reference_genomes: list[dict] | None = None,
        assemblies: list[dict] | None = None,
    ):
        self.reference_genomes = reference_genomes or []
        self.assemblies = assemblies or []
        self.gene_counts = gene_counts or {}
        self.reports = reports or []
        self.counts = counts or {}
        self.fail = fail
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = unquote(str(request.url))
        if self.fail and self.fail in url:
            return httpx.Response(500)
        if url.endswith("/counts"):
            report = [{"gene_type": t, "count": c} for t, c in self.gene_counts.items()]
            return httpx.Response(200, json={"report": report} if report else {})
        if "/genome/taxon/" in url:
            params = parse_qs(urlparse(str(request.url)).query)
            if "filters.reference_only" in params:
                found = self.reference_genomes
            else:
                found = self.assemblies
            if not found:
                return httpx.Response(200, json={})
            if params.get("returned_content") == ["ASSM_ACC"]:
                accessions = [{"accession": r["accession"]} for r in found]
                return httpx.Response(
                    200,
                    json={"reports": accessions[:1], "total_count": len(found)},
                )
            size = int(params["page_size"][0])
            return httpx.Response(
                200, json={"reports": found[:size], "total_count": len(found)}
            )
        if url.endswith("/dataset_report"):
            return httpx.Response(
                200, json={"reports": self.reports} if self.reports else {}
            )
        term = parse_qs(urlparse(str(request.url)).query)["term"][0]
        count = next((c for key, c in self.counts.items() if key in term), 0)
        return httpx.Response(200, json={"esearchresult": {"count": str(count)}})

    def client(self, api_key: str | None = None, email: str | None = "t@example.org"):
        client = NcbiClient(api_key, email, transport=httpx.MockTransport(self.handler))
        client._min_interval = 0.0
        return client

    def summary(self, **kwargs) -> GeneticsSummary:
        return GeneticsSummary(self.client(), **kwargs)


# ---------------------------------------------------------------------------
# Names and references
# ---------------------------------------------------------------------------


class TestNames:
    @pytest.mark.parametrize(
        "query, expected",
        [
            ("danaus_plexippus", "Danaus plexippus"),
            ("Panthera leo persica", "Panthera leo persica"),
            ("Rattus  everetti", "Rattus everetti"),
            ("danaus", None),
            ('Danaus plexippus"[Organism] OR human', None),
            ("Danaus plexippus 1", None),
        ],
    )
    def test_only_species_names_reach_ncbi(self, query, expected):
        assert normalize_species_name(query) == expected

    def test_prefers_the_species_own_mitogenome(self):
        reports = [
            mito_report("Panthera leo persica", "NC_018053.1"),
            mito_report("Panthera leo", "NC_028302.1"),
        ]
        reference = choose_reference(reports, "Panthera leo")
        assert reference.refseq_accession == "NC_028302.1"
        assert reference.organism_name == "Panthera leo"

    def test_falls_back_to_a_subspecies_mitogenome(self):
        reference = choose_reference(
            [mito_report("Panthera leo persica")], "Panthera leo"
        )
        assert reference.organism_name == "Panthera leo persica"
        assert reference.gene_count == 37

    def test_no_reports_means_no_reference(self):
        assert choose_reference([], "Rattus everetti") is None

    def test_reads_assembly_stats_and_annotation(self):
        assembly = to_assembly(
            genome_report("Danaus plexippus", reference=True, annotated=True)
        )
        assert assembly.is_reference is True
        # Datasets sends the length as a string.
        assert assembly.genome_size == 245173502
        assert assembly.contig_n50 == 3940764
        assert assembly.gc_percent == 32.0
        assert assembly.annotation.protein_coding == 12804
        assert assembly.annotation.pseudogenes is None
        assert assembly.annotation.busco_complete == pytest.approx(0.9947)

    def test_best_assembly_is_most_complete_then_most_contiguous(self):
        reports = [
            genome_report("Morpho helenor", "GCA_1", level="Contig", contig_n50=9e7),
            genome_report("Morpho helenor", "GCA_2", level="Scaffold", contig_n50=10),
            genome_report("Morpho helenor", "GCA_3", level="Scaffold", contig_n50=20),
        ]
        assert choose_assembly(reports, "Morpho helenor").accession == "GCA_3"

    def test_best_assembly_prefers_the_species_own(self):
        reports = [
            genome_report("Morpho helenor peleides", "GCA_1", level="Chromosome"),
            genome_report("Morpho helenor", "GCA_2", level="Contig"),
        ]
        assert choose_assembly(reports, "Morpho helenor").accession == "GCA_2"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestGeneticsSummary:
    def test_reports_mitochondrial_data_without_an_annotated_genome(self):
        fake = FakeNcbi(
            counts={"CYTB[gene]": 21, "complete genome": 0, "mitochondrion": 23}
        )
        payload = asyncio.run(fake.summary().summarize("rattus_everetti"))

        assert payload.species == "Rattus everetti"
        assert payload.gene_types == {}
        assert payload.partial is False
        mito = payload.mitochondrion
        assert mito.reference is None
        assert mito.sequence_count == 23
        assert mito.complete_genome_count == 0
        assert [m.marker for m in mito.markers] == [m[0] for m in MITOCHONDRIAL_MARKERS]
        cytb = next(m for m in mito.markers if m.marker == "CYTB")
        assert cytb.count == 21
        assert cytb.query.startswith(organism_query("Rattus everetti"))

    def test_includes_annotated_genes_and_the_reference(self):
        fake = FakeNcbi(
            gene_counts={"PROTEIN_CODING": 19491, "tRNA": 713},
            reports=[mito_report("Panthera leo")],
            counts={"complete genome": 19, "mitochondrion": 343},
        )
        payload = asyncio.run(fake.summary().summarize("Panthera leo"))
        assert payload.gene_types == {"PROTEIN_CODING": 19491, "tRNA": 713}
        assert payload.mitochondrion.reference.length == 17044
        assert payload.mitochondrion.complete_genome_count == 19

    def test_skips_the_breakdown_when_there_is_nothing_mitochondrial(self):
        fake = FakeNcbi()
        payload = asyncio.run(fake.summary().summarize("Fooia barus"))
        # Gene counts, reference genome, assembly count, organelle report,
        # one esearch: nothing else.
        assert len(fake.requests) == 5
        assert payload.nuclear.assembly is None
        assert payload.nuclear.assembly_count == 0
        assert payload.mitochondrion.markers == []
        assert payload.mitochondrion.complete_genome_count == 0
        assert payload.partial is False

    def test_includes_the_reference_genome(self):
        reference = genome_report("Danaus plexippus", reference=True, annotated=True)
        fake = FakeNcbi(
            reference_genomes=[reference],
            assemblies=[reference, genome_report("Danaus plexippus", "GCA_9")],
        )
        payload = asyncio.run(fake.summary().summarize("Danaus plexippus"))
        assert payload.nuclear.assembly.accession == "GCF_018135715.1"
        assert payload.nuclear.assembly.is_reference is True
        assert payload.nuclear.assembly_count == 2
        # The reference was found, so the assemblies were only counted.
        assert len(fake.requests) == 5

    def test_falls_back_to_the_best_assembly_without_a_reference(self):
        fake = FakeNcbi(
            assemblies=[
                genome_report("Morpho helenor", "GCA_1", level="Contig"),
                genome_report("Morpho helenor", "GCA_2", level="Scaffold"),
            ]
        )
        payload = asyncio.run(fake.summary().summarize("Morpho helenor"))
        assert payload.nuclear.assembly.accession == "GCA_2"
        assert payload.nuclear.assembly.is_reference is False
        assert payload.nuclear.assembly_count == 2
        assert payload.partial is False
        assert len(fake.requests) == 6

    def test_a_failed_call_makes_the_result_partial(self):
        fake = FakeNcbi(counts={"mitochondrion": 5}, fail="/counts")
        payload = asyncio.run(fake.summary().summarize("Rattus everetti"))
        assert payload.partial is True
        assert payload.gene_types is None
        assert payload.mitochondrion.sequence_count == 5

    def test_a_slow_lookup_returns_what_it_has(self):
        fake = FakeNcbi(counts={"mitochondrion": 5})
        client = fake.client()
        # The first five calls finish by ~0.2 s; all eleven would take ~0.5 s.
        client._min_interval = 0.05
        summary = GeneticsSummary(client, deadline=0.35)
        payload = asyncio.run(summary.summarize("Rattus everetti"))
        assert payload.partial is True
        assert payload.mitochondrion.sequence_count == 5
        assert len(payload.mitochondrion.markers) < len(MITOCHONDRIAL_MARKERS)

    def test_caches_and_shares_in_flight_lookups(self):
        fake = FakeNcbi(counts={"mitochondrion": 5})
        summary = fake.summary()

        async def run():
            first, second = await asyncio.gather(
                summary.summarize("Rattus everetti"),
                summary.summarize("rattus_everetti"),
            )
            third = await summary.summarize("Rattus everetti")
            return first, second, third

        first, second, third = asyncio.run(run())
        assert first == second == third
        # One lookup: 5 first-phase calls + complete genome + 5 markers.
        assert len(fake.requests) == 5 + 1 + len(MITOCHONDRIAL_MARKERS)

    def test_partial_results_are_cached_briefly(self):
        fake = FakeNcbi(fail="/counts")
        summary = fake.summary()
        asyncio.run(summary.summarize("Rattus everetti"))
        expires_at, _ = summary._cache._entries["Rattus everetti"]
        complete = FakeNcbi().summary()
        asyncio.run(complete.summarize("Rattus everetti"))
        complete_expires_at, _ = complete._cache._entries["Rattus everetti"]
        assert expires_at < complete_expires_at - 60 * 60

    def test_refuses_new_lookups_past_the_pending_limit(self):
        release = asyncio.Event()

        class SlowSummary(GeneticsSummary):
            async def _fill(self, payload):
                await release.wait()

        summary = SlowSummary(FakeNcbi().client(), max_pending=1)

        async def run():
            first = asyncio.create_task(summary.summarize("Rattus everetti"))
            await asyncio.sleep(0)
            with pytest.raises(GeneticsBusy):
                await summary.summarize("Danaus plexippus")
            # A second reader of the in-flight species still shares it.
            second = asyncio.create_task(summary.summarize("Rattus everetti"))
            await asyncio.sleep(0)
            release.set()
            return await first, await second

        first, second = asyncio.run(run())
        assert first == second


# ---------------------------------------------------------------------------
# NCBI etiquette
# ---------------------------------------------------------------------------


class TestNcbiClient:
    def test_identifies_itself(self):
        fake = FakeNcbi()
        asyncio.run(fake.client().nuccore_count("x"))
        request = fake.requests[0]
        params = parse_qs(urlparse(str(request.url)).query)
        assert params["tool"] == ["BioCosmos"]
        assert params["email"] == ["t@example.org"]
        assert "api_key" not in params
        assert "api-key" not in request.headers
        assert "mailto:t@example.org" in request.headers["User-Agent"]

    def test_sends_the_api_key_to_both_services(self):
        fake = FakeNcbi()
        client = fake.client(api_key="secret")

        async def run():
            await client.nuccore_count("x")
            await client.gene_type_counts("Danaus plexippus")

        asyncio.run(run())
        esearch, datasets = fake.requests
        assert parse_qs(urlparse(str(esearch.url)).query)["api_key"] == ["secret"]
        assert datasets.headers["api-key"] == "secret"

    def test_paces_by_whether_there_is_a_key(self):
        assert NcbiClient()._min_interval == MIN_INTERVAL_WITHOUT_KEY
        assert NcbiClient("secret")._min_interval == MIN_INTERVAL_WITH_KEY
        # Within NCBI's 3 and 10 requests per second.
        assert MIN_INTERVAL_WITHOUT_KEY >= 1 / 3
        assert MIN_INTERVAL_WITH_KEY >= 1 / 10

    def test_pacing_spaces_request_starts(self):
        fake = FakeNcbi()
        client = fake.client()
        client._min_interval = 0.05

        async def run():
            loop = asyncio.get_running_loop()
            start = loop.time()
            await asyncio.gather(*(client.nuccore_count("x") for _ in range(4)))
            return loop.time() - start

        assert asyncio.run(run()) >= 0.15

    def test_backs_off_once_on_429(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"esearchresult": {"count": "7"}})

        client = NcbiClient(transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        assert asyncio.run(client.nuccore_count("x")) == 7
        assert len(calls) == 2

    def test_gives_up_after_a_second_429(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        client = NcbiClient(transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        with pytest.raises(NcbiError):
            asyncio.run(client.nuccore_count("x"))

    def test_an_esearch_error_is_not_a_zero(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"esearchresult": {"ERROR": "bad"}})

        client = NcbiClient(transport=httpx.MockTransport(handler))
        client._min_interval = 0.0
        with pytest.raises(NcbiError):
            asyncio.run(client.nuccore_count("x"))

    def test_keeps_only_mitochondrial_organelles(self):
        fake = FakeNcbi(
            reports=[
                mito_report("Arabidopsis thaliana"),
                {**mito_report("Arabidopsis thaliana"), "description": "Chloroplast"},
            ]
        )
        reports = asyncio.run(fake.client().mitogenome_reports("Arabidopsis thaliana"))
        assert len(reports) == 1


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class StubSummary:
    def __init__(self, result):
        self.result = result

    async def summarize(self, name):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def router_client(result) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_genetics_summary] = lambda: StubSummary(result)
    return TestClient(app)


def payload(**kwargs) -> GeneticsPayload:
    return GeneticsPayload(
        species="Rattus everetti",
        mitochondrion=Mitochondrion(
            query=organism_query("Rattus everetti"), sequence_count=23
        ),
        **kwargs,
    )


class TestGeneticsRouter:
    def test_complete_result_is_cached_for_a_day(self):
        response = router_client(payload(gene_types={})).get(
            "/species/rattus_everetti/genetics"
        )
        assert response.status_code == 200
        assert "max-age=86400" in response.headers["Cache-Control"]
        body = response.json()
        assert body["geneTypes"] == {}
        assert body["nuclear"] == {"assembly": None, "assemblyCount": None}
        assert body["mitochondrion"]["sequenceCount"] == 23
        assert body["mitochondrion"]["completeGenomeCount"] is None

    def test_partial_result_is_cached_briefly(self):
        response = router_client(payload(partial=True)).get(
            "/species/rattus_everetti/genetics"
        )
        assert "max-age=300" in response.headers["Cache-Control"]
        assert response.json()["partial"] is True

    def test_non_species_returns_404(self):
        response = router_client(None).get("/species/rattus/genetics")
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"

    def test_busy_returns_503_to_retry(self):
        response = router_client(GeneticsBusy("full")).get(
            "/species/rattus_everetti/genetics"
        )
        assert response.status_code == 503
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Retry-After"] == "5"
