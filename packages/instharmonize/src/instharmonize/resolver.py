"""Resolve institution codes, one code at a time, strongest evidence first.

For each code, in order:

1. A curated override.
2. A full name written in the code field ("Hartland Nature Club").
3. GRSciColl's dataset-aware lookup, when it reports an exact match -- an
   identifier such as a ROR or GRSciColl URL in `institutionID`, or a code
   already mapped to the dataset.
4. GRSciColl institutions with the same code, accepted only when the name
   agrees with the GBIF publisher. For an aggregating publisher (one that
   publishes several codes, such as a national biodiversity portal) the name
   says nothing, so a single active candidate in the publisher's country is
   accepted instead.
5. The GBIF publishing organization itself, when its name spells out the code.

Anything else stays unresolved. A bare code is better than a confident wrong
name: GRSciColl alone maps `KSU` to King Saud University, and `UI` to the
Bureau of Land Management.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor

from instharmonize.gbif import (
    GbifRegistry,
    LookupMatch,
    Publisher,
    Registry,
    RegistryError,
    RegistryInstitution,
)
from instharmonize.models import Institution, InstitutionRecord, MatchSource
from instharmonize.names import (
    code_matches_name,
    fold,
    is_placeholder_code,
    name_similarity,
    split_verbatim_name,
)
from instharmonize.overrides import Override, load_overrides, overrides_digest

# Bumped whenever a change to the rules could change an answer, so a caller
# caching results knows to resolve again.
RESOLVER_VERSION = 1

# The name_similarity at which a registry name and a publisher name are taken
# to be the same institution.
NAME_AGREEMENT = 0.6

# Datasets tried per code, most occurrences first. A code spread across many
# datasets (one per family, say) is almost always the same institution.
MAX_DATASETS_PER_CODE = 3

_EXACT_MATCHES = (LookupMatch.EXACT, LookupMatch.EXPLICIT_MAPPING)


class InstitutionResolver:
    def __init__(
        self,
        registry: Registry | None = None,
        overrides: Mapping[str, Override] | None = None,
        max_workers: int = 8,
    ):
        self.registry: Registry = registry or GbifRegistry()
        self.overrides = dict(load_overrides() if overrides is None else overrides)
        self.max_workers = max_workers

    @property
    def fingerprint(self) -> str:
        """Changes when either the rules or the curated entries do."""
        return f"v{RESOLVER_VERSION}:{overrides_digest(self.overrides)}"

    def resolve_all(self, records: Iterable[InstitutionRecord]) -> dict[str, Institution]:
        """Resolve every distinct code in `records`, keyed on the trimmed code."""
        by_code: dict[str, list[InstitutionRecord]] = defaultdict(list)
        for record in records:
            if is_placeholder_code(record.institution_code):
                continue
            by_code[record.institution_code.strip()].append(record)
        aggregators = _aggregating_publishers(by_code)

        def resolve_one(item: tuple[str, list[InstitutionRecord]]) -> Institution:
            code, code_records = item
            code_records.sort(key=lambda r: r.occurrences, reverse=True)
            return self._resolve_code(code, code_records, aggregators)

        with ThreadPoolExecutor(max_workers=max(1, self.max_workers)) as pool:
            resolved = pool.map(resolve_one, by_code.items())
            return {institution.code: institution for institution in resolved}

    def resolve(self, record: InstitutionRecord) -> Institution:
        """Resolve a single code from one dataset."""
        code = record.institution_code.strip()
        return self.resolve_all([record]).get(code) or Institution(code=code)

    def _resolve_code(
        self, code: str, records: list[InstitutionRecord], aggregators: frozenset[str]
    ) -> Institution:
        override = self.overrides.get(code)
        if override is not None:
            return self._curated(code, override, records)

        verbatim = split_verbatim_name(code)
        if verbatim is not None:
            return Institution(code=code, name=verbatim[0], source=MatchSource.VERBATIM)

        retry = False
        for record in records[:MAX_DATASETS_PER_CODE]:
            aggregated = bool(record.publisher) and fold(record.publisher or "") in aggregators
            try:
                found = self._from_registry(code, record, aggregated)
            except RegistryError:
                retry = True
                continue
            if found is not None:
                return found
        return Institution(code=code, retry=retry)

    def _curated(
        self, code: str, override: Override, records: list[InstitutionRecord]
    ) -> Institution:
        publisher: Publisher | None = None
        retry = False
        if override.use_publisher:
            try:
                publisher = self._publisher(records[0]) if records else None
            except RegistryError:
                retry = True
        name = override.name or (publisher.name if publisher else None)
        return Institution(
            code=code,
            name=name,
            homepage=override.homepage or (publisher.homepage if publisher else None),
            country=override.country or (publisher.country if publisher else None),
            source=MatchSource.CURATED if name else MatchSource.UNRESOLVED,
            retry=retry and name is None,
        )

    def _from_registry(
        self, code: str, record: InstitutionRecord, aggregated: bool
    ) -> Institution | None:
        lookup = self.registry.lookup(
            code,
            record.dataset_key,
            record.institution_id,
            record.owner_institution_code,
        )
        if lookup.match in _EXACT_MATCHES and lookup.institution_key:
            institution = self.registry.institution(lookup.institution_key)
            if institution is not None:
                return self._from_grscicoll(
                    code, institution, MatchSource.GRSCICOLL_EXACT, record, aggregated
                )

        candidates = self.registry.institutions_by_code(code)
        fuzzy_key = lookup.institution_key if lookup.match is LookupMatch.FUZZY else None
        if fuzzy_key and all(c.key != fuzzy_key for c in candidates):
            fuzzy = self.registry.institution(fuzzy_key)
            candidates = [*candidates, fuzzy] if fuzzy else candidates
        chosen = _choose_candidate(candidates, record, aggregated)
        if chosen is not None:
            return self._from_grscicoll(
                code, chosen, MatchSource.GRSCICOLL_VERIFIED, record, aggregated
            )

        publisher = self._publisher(record)
        name = publisher.name if publisher else record.publisher
        if name and code_matches_name(code, name):
            return Institution(
                code=code,
                name=name,
                homepage=publisher.homepage if publisher else None,
                country=(publisher.country if publisher else None) or record.publishing_country,
                source=MatchSource.GBIF_PUBLISHER,
            )
        return None

    def _from_grscicoll(
        self,
        code: str,
        institution: RegistryInstitution,
        source: MatchSource,
        record: InstitutionRecord,
        aggregated: bool,
    ) -> Institution:
        homepage = institution.homepage
        if homepage is None and not aggregated:
            # GRSciColl often lacks a homepage the publisher record has. Only
            # borrowed when the two names agree, i.e. they are one institution.
            publisher = self._publisher(record)
            if publisher and name_similarity(publisher.name, institution.name) >= NAME_AGREEMENT:
                homepage = publisher.homepage
        return Institution(
            code=code,
            name=institution.name,
            homepage=homepage,
            country=institution.country,
            grscicoll_key=institution.key,
            source=source,
        )

    def _publisher(self, record: InstitutionRecord) -> Publisher | None:
        if not record.dataset_key:
            return None
        return self.registry.dataset_publisher(record.dataset_key)


def _aggregating_publishers(by_code: Mapping[str, list[InstitutionRecord]]) -> frozenset[str]:
    """Publishers seen with more than one code, by folded name.

    Such a publisher is a portal or a host, not the holding institution, so
    its name is no evidence for or against a candidate.
    """
    codes_by_publisher: dict[str, set[str]] = defaultdict(set)
    for code, records in by_code.items():
        for record in records:
            if record.publisher:
                codes_by_publisher[fold(record.publisher)].add(fold(code))
    return frozenset(name for name, codes in codes_by_publisher.items() if len(codes) > 1)


def _choose_candidate(
    candidates: list[RegistryInstitution], record: InstitutionRecord, aggregated: bool
) -> RegistryInstitution | None:
    evidence = [record.publisher]
    owner = record.owner_institution_code
    if owner and split_verbatim_name(owner) is not None:
        evidence.append(owner)
    texts = [text for text in evidence if text]

    scored: list[tuple[float, bool, RegistryInstitution]] = []
    for candidate in candidates:
        score = max((name_similarity(candidate.name, text) for text in texts), default=0.0)
        if score >= NAME_AGREEMENT:
            scored.append((score, candidate.active, candidate))
    if scored:
        return max(scored, key=lambda item: (item[0], item[1]))[2]

    if aggregated and record.publishing_country:
        local = [c for c in candidates if c.country == record.publishing_country]
        active = [c for c in local if c.active] or local
        if len(active) == 1:
            return active[0]
    return None
