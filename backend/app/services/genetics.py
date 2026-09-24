"""What NCBI holds on a species' genes and mitochondrial DNA.

The genetics tab showed only NCBI Gene's annotated-gene counts, which exist
only for species with an annotated genome, so a species known from a few
dozen mitochondrial sequences read as having no genetic data at all. This
assembles, in one payload:

* the reference nuclear genome assembly, or the best available one, with
  its size, contiguity and annotation, and how many assemblies NCBI holds
  (Datasets genome reports);
* annotated genes by type (NCBI Datasets gene counts);
* the RefSeq reference mitogenome, if one exists (Datasets organelle report);
* how many GenBank nucleotide records are mitochondrial, how many of those
  are complete mitogenomes, and how many cover the markers most used in
  systematics (E-utilities esearch counts).

Every answer is cached for a week, and concurrent requests for one species
share a single set of NCBI calls. Lookups are bounded twice over so a burst
of distinct species cannot pile up behind NCBI's rate limit: each lookup has
a deadline, after which it returns what it has as partial, and past
``MAX_PENDING_LOOKUPS`` uncached lookups in flight, new ones are refused
rather than queued.
"""

import asyncio
import logging
import re

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .ncbi import NcbiClient, NcbiError, get_ncbi_client
from .ttl_cache import TtlCache

logger = logging.getLogger(__name__)

# A week: sequences accrue slowly, and a stale count costs a reader little.
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
# Long enough to absorb a burst of reloads, short enough to outlive no outage.
PARTIAL_CACHE_TTL_SECONDS = 60 * 5
CACHE_MAX_ENTRIES = 2048
# At most twelve NCBI calls at under 3 per second take about 4.5 s alone; the
# rest is headroom for other lookups sharing the rate limit.
LOOKUP_DEADLINE_SECONDS = 12.0
MAX_PENDING_LOOKUPS = 32

# `Genus epithet` or `Genus epithet subspecies`, as NCBI's taxonomy spells
# them. Anything else never reaches NCBI.
_SPECIES_NAME = re.compile(
    r"^[A-Z][a-z]+(?:-[a-z]+)? [a-z]+(?:-[a-z]+)*(?: [a-z]+(?:-[a-z]+)*)?$"
)

# How complete an assembly is, best first, for choosing among assemblies when
# a species has no designated reference genome.
ASSEMBLY_LEVELS = ("Complete Genome", "Chromosome", "Scaffold", "Contig")
# Enough to find the best of a species' assemblies without paging; a species
# with more than this almost always has a designated reference anyway.
ASSEMBLY_CANDIDATES = 10

# (key, label, Entrez query). The queries were checked against a vertebrate
# (Panthera leo) and an insect (Danaus plexippus): genes are annotated under
# either the vertebrate (COX1, CYTB) or invertebrate (COI, cob) symbol, and
# ribosomal RNAs and the control region are more reliably found by title.
MITOCHONDRIAL_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("COI", "Cytochrome c oxidase I (COI)", "COI[gene] OR COX1[gene] OR CO1[gene]"),
    ("CYTB", "Cytochrome b (cytb)", "CYTB[gene] OR cob[gene]"),
    ("12S", "12S ribosomal RNA", "rrnS[gene] OR 12S[title]"),
    ("16S", "16S ribosomal RNA", "rrnL[gene] OR 16S[title]"),
    ("CR", "Control region (D-loop)", 'D-loop[title] OR "control region"[title]'),
)


class GeneticsBusy(Exception):
    """Too many uncached lookups are already waiting on NCBI."""


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MitogenomeReference(_Model):
    refseq_accession: str | None = None
    genbank_accession: str | None = None
    # May be a subspecies when the species itself has no RefSeq mitogenome.
    organism_name: str | None = None
    length: int | None = None
    topology: str | None = None
    gene_count: int | None = None
    submission_date: str | None = None


class GenomeAnnotation(_Model):
    name: str | None = None
    provider: str | None = None
    release_date: str | None = None
    report_url: str | None = None
    total_genes: int | None = None
    protein_coding: int | None = None
    non_coding: int | None = None
    pseudogenes: int | None = None
    # BUSCO: the share (0-1) of conserved single-copy genes found complete.
    busco_complete: float | None = None
    busco_lineage: str | None = None


class GenomeAssembly(_Model):
    accession: str
    paired_accession: str | None = None
    assembly_name: str | None = None
    # May be a subspecies, as for the mitogenome.
    organism_name: str | None = None
    # NCBI's designated reference genome, rather than the best of the rest.
    is_reference: bool = False
    assembly_level: str | None = None
    release_date: str | None = None
    submitter: str | None = None
    sequencing_tech: str | None = None
    genome_size: int | None = None
    chromosome_count: int | None = None
    contig_count: int | None = None
    contig_n50: int | None = None
    scaffold_count: int | None = None
    scaffold_n50: int | None = None
    gc_percent: float | None = None
    coverage: str | None = None
    annotation: GenomeAnnotation | None = None


class NuclearGenome(_Model):
    assembly: GenomeAssembly | None = None
    # None when the count could not be fetched; 0 when NCBI has none.
    assembly_count: int | None = None


class MarkerCount(_Model):
    marker: str
    label: str
    count: int
    # The Entrez query behind the count, so the page can link to the records.
    query: str


class Mitochondrion(_Model):
    reference: MitogenomeReference | None = None
    # None when that count could not be fetched; 0 when NCBI has none.
    sequence_count: int | None = None
    complete_genome_count: int | None = None
    markers: list[MarkerCount] = []
    query: str


class GeneticsPayload(_Model):
    species: str
    # None when the gene counts could not be fetched.
    gene_types: dict[str, int] | None = None
    nuclear: NuclearGenome = Field(default_factory=NuclearGenome)
    mitochondrion: Mitochondrion
    # True when an NCBI request failed or timed out, so something is missing.
    partial: bool = False


def normalize_species_name(query: str) -> str | None:
    """`Danaus plexippus` from a name or slug; None if it is not a species."""
    parts = query.replace("_", " ").split()
    if len(parts) < 2:
        return None
    name = " ".join([parts[0].capitalize(), *(p.lower() for p in parts[1:])])
    return name if _SPECIES_NAME.match(name) else None


def organism_query(species: str) -> str:
    # `noexp` keeps the count to the taxon itself plus its subspecies, rather
    # than exploding into whatever NCBI files beneath it.
    return f'"{species}"[Organism:noexp] AND mitochondrion[filter]'


def choose_reference(reports: list[dict], species: str) -> MitogenomeReference | None:
    """The species' own RefSeq mitogenome, else the first of a subspecies."""
    if not reports:
        return None

    def name_of(report: dict) -> str:
        return str((report.get("organism") or {}).get("organism_name", ""))

    report = next((r for r in reports if name_of(r) == species), reports[0])
    refseq = report.get("refseq") or {}
    genbank = report.get("genbank") or {}
    return MitogenomeReference(
        refseq_accession=refseq.get("accession"),
        genbank_accession=genbank.get("accession"),
        organism_name=name_of(report) or None,
        length=report.get("length"),
        topology=report.get("topology"),
        gene_count=report.get("gene_count"),
        submission_date=refseq.get("submission_date") or genbank.get("submission_date"),
    )


def _int(value) -> int | None:
    """Datasets sends large numbers as strings and small ones as numbers."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_assembly(report: dict) -> GenomeAssembly | None:
    """The fields the page shows from a Datasets genome report."""
    accession = report.get("accession") or report.get("current_accession")
    if not accession:
        return None
    info = report.get("assembly_info") or {}
    stats = report.get("assembly_stats") or {}
    annotation = report.get("annotation_info") or None
    if annotation:
        genes = (annotation.get("stats") or {}).get("gene_counts") or {}
        busco = annotation.get("busco") or {}
        annotation = GenomeAnnotation(
            name=annotation.get("name"),
            provider=annotation.get("provider"),
            release_date=annotation.get("release_date"),
            report_url=annotation.get("report_url"),
            total_genes=_int(genes.get("total")),
            protein_coding=_int(genes.get("protein_coding")),
            non_coding=_int(genes.get("non_coding")),
            pseudogenes=_int(genes.get("pseudogene")),
            busco_complete=_float(busco.get("complete")),
            busco_lineage=busco.get("busco_lineage"),
        )
    return GenomeAssembly(
        accession=accession,
        paired_accession=report.get("paired_accession"),
        assembly_name=info.get("assembly_name"),
        organism_name=(report.get("organism") or {}).get("organism_name"),
        is_reference=info.get("refseq_category") == "reference genome",
        assembly_level=info.get("assembly_level"),
        release_date=info.get("release_date"),
        submitter=info.get("submitter"),
        sequencing_tech=info.get("sequencing_tech"),
        genome_size=_int(stats.get("total_sequence_length")),
        chromosome_count=_int(stats.get("total_number_of_chromosomes")),
        contig_count=_int(stats.get("number_of_contigs")),
        contig_n50=_int(stats.get("contig_n50")),
        scaffold_count=_int(stats.get("number_of_scaffolds")),
        scaffold_n50=_int(stats.get("scaffold_n50")),
        gc_percent=_float(stats.get("gc_percent")),
        coverage=stats.get("genome_coverage"),
        annotation=annotation,
    )


def choose_assembly(reports: list[dict], species: str) -> GenomeAssembly | None:
    """The best of a species' assemblies: its own over a subspecies', then
    the most complete level, then the longest contigs, then the newest."""
    assemblies = [a for a in map(to_assembly, reports) if a is not None]
    if not assemblies:
        return None

    def rank(assembly: GenomeAssembly) -> tuple:
        level = assembly.assembly_level or ""
        return (
            assembly.organism_name == species,
            assembly.annotation is not None,
            -ASSEMBLY_LEVELS.index(level) if level in ASSEMBLY_LEVELS else -99,
            assembly.contig_n50 or 0,
            assembly.release_date or "",
        )

    return max(assemblies, key=rank)


class GeneticsSummary:
    """Cached, rate-limited genetic summaries of species."""

    def __init__(
        self,
        ncbi: NcbiClient,
        *,
        cache: TtlCache[GeneticsPayload] | None = None,
        deadline: float = LOOKUP_DEADLINE_SECONDS,
        max_pending: int = MAX_PENDING_LOOKUPS,
    ):
        self.ncbi = ncbi
        self._cache = cache or TtlCache(CACHE_TTL_SECONDS, CACHE_MAX_ENTRIES)
        self.deadline = deadline
        self.max_pending = max_pending
        self._loop: asyncio.AbstractEventLoop | None = None
        self._inflight: dict[str, asyncio.Task] = {}

    async def summarize(self, query: str) -> GeneticsPayload | None:
        """The summary for a species, or None if `query` is not a species name.

        Raises GeneticsBusy when the lookup would have to queue behind too
        many others.
        """
        species = normalize_species_name(query)
        if species is None:
            return None
        cached = self._cache.get(species)
        if cached is not None:
            return cached

        loop = asyncio.get_running_loop()
        if loop is not self._loop:
            self._loop = loop
            self._inflight = {}

        # Two readers opening the same species page share one lookup. The
        # task is shielded, so a reader closing the tab does not cancel the
        # lookup for the others, and its result still reaches the cache.
        task = self._inflight.get(species)
        if task is None:
            if len(self._inflight) >= self.max_pending:
                raise GeneticsBusy(
                    f"{len(self._inflight)} genetics lookups already in flight."
                )
            task = loop.create_task(self._lookup(species))
            self._inflight[species] = task
            task.add_done_callback(lambda _: self._inflight.pop(species, None))
        return await asyncio.shield(task)

    async def _lookup(self, species: str) -> GeneticsPayload:
        payload = GeneticsPayload(
            species=species,
            mitochondrion=Mitochondrion(query=organism_query(species)),
        )
        try:
            await asyncio.wait_for(self._fill(payload), timeout=self.deadline)
        except TimeoutError:
            logger.warning(f"Genetics lookup for {species} hit its deadline.")
            payload.partial = True

        self._cache.set(
            species,
            payload,
            ttl=PARTIAL_CACHE_TTL_SECONDS if payload.partial else None,
        )
        return payload

    async def _fill(self, payload: GeneticsPayload) -> None:
        """Fetch into `payload` as results arrive, so a timeout keeps what
        already came back."""
        species = payload.species
        mito = payload.mitochondrion
        nuclear = payload.nuclear

        async def gene_types() -> None:
            payload.gene_types = await self.ncbi.gene_type_counts(species)

        async def reference_genome() -> None:
            reports = await self.ncbi.reference_genome_reports(species)
            nuclear.assembly = to_assembly(reports[0]) if reports else None

        async def assembly_count() -> None:
            _, total = await self.ncbi.genome_assemblies(
                species, 1, accessions_only=True
            )
            nuclear.assembly_count = total

        async def best_assembly() -> None:
            reports, _ = await self.ncbi.genome_assemblies(species, ASSEMBLY_CANDIDATES)
            nuclear.assembly = choose_assembly(reports, species)

        async def reference() -> None:
            reports = await self.ncbi.mitogenome_reports(species)
            mito.reference = choose_reference(reports, species)

        async def sequence_count() -> None:
            mito.sequence_count = await self.ncbi.nuccore_count(mito.query)

        await self._gather(
            payload,
            gene_types(),
            reference_genome(),
            assembly_count(),
            reference(),
            sequence_count(),
        )

        # Most species have no genome assembly and no mitochondrial records;
        # asking for the details of nothing would spend requests to learn
        # nothing, so each follow-up runs only when there is something to see.
        follow_ups = []
        if nuclear.assembly is None and (nuclear.assembly_count or 0) > 0:
            follow_ups.append(best_assembly())

        if mito.sequence_count == 0 and mito.reference is None:
            mito.complete_genome_count = 0
            if follow_ups:
                await self._gather(payload, *follow_ups)
            return

        async def complete_count() -> None:
            mito.complete_genome_count = await self.ncbi.nuccore_count(
                f"{mito.query} AND complete genome[title]"
            )

        markers: dict[str, MarkerCount] = {}

        async def marker_count(key: str, label: str, term: str) -> None:
            query = f"{mito.query} AND ({term})"
            count = await self.ncbi.nuccore_count(query)
            markers[key] = MarkerCount(
                marker=key, label=label, count=count, query=query
            )

        try:
            await self._gather(
                payload,
                *follow_ups,
                complete_count(),
                *(marker_count(*marker) for marker in MITOCHONDRIAL_MARKERS),
            )
        finally:
            # Kept in the fixed order, including after a timeout.
            mito.markers = [
                markers[key] for key, _, _ in MITOCHONDRIAL_MARKERS if key in markers
            ]

    @staticmethod
    async def _gather(payload: GeneticsPayload, *calls) -> None:
        results = await asyncio.gather(*calls, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                if not isinstance(result, NcbiError):
                    raise result
                logger.warning(
                    f"Genetics lookup incomplete for {payload.species}: {result}"
                )
                payload.partial = True

    def clear_cache(self) -> None:
        self._cache.clear()


_shared_summary: GeneticsSummary | None = None


def get_genetics_summary() -> GeneticsSummary:
    """The process-wide service, so every request shares one cache."""
    global _shared_summary
    if _shared_summary is None:
        _shared_summary = GeneticsSummary(get_ncbi_client())
    return _shared_summary
