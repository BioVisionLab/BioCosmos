from __future__ import annotations

from instharmonize.gbif import LookupMatch, LookupResult, Publisher, RegistryInstitution
from instharmonize.models import InstitutionRecord, MatchSource
from instharmonize.overrides import Override
from instharmonize.resolver import InstitutionResolver

MCZ = RegistryInstitution(
    key="mcz",
    code="MCZ",
    name="Harvard University, Museum of Comparative Zoology",
    country="US",
    homepage="https://mcz.harvard.edu/",
)
BLM = RegistryInstitution(
    key="blm", code="UI", name="Bureau of Land Management, U.S. Department of the Interior"
)


def resolver(registry, overrides=None) -> InstitutionResolver:
    return InstitutionResolver(registry=registry, overrides=overrides or {}, max_workers=2)


def record(code: str, **fields) -> InstitutionRecord:
    return InstitutionRecord(institution_code=code, **fields)


def test_exact_lookup_is_accepted_without_a_name_check(registry) -> None:
    registry.by_code["MCZ"] = [MCZ]
    registry.lookups[("MCZ", "d1")] = LookupResult(LookupMatch.EXACT, "mcz")

    result = resolver(registry).resolve(record("MCZ", dataset_key="d1", publisher="Anyone"))

    assert result.name == MCZ.name
    assert result.homepage == MCZ.homepage
    assert result.grscicoll_key == "mcz"
    assert result.source is MatchSource.GRSCICOLL_EXACT


def test_fuzzy_code_match_needs_an_agreeing_publisher(registry) -> None:
    """GRSciColl pairs UI with the BLM; the Idaho publisher wins instead."""
    registry.by_code["UI"] = [BLM]
    registry.lookups[("UI", "d1")] = LookupResult(LookupMatch.FUZZY, "blm")
    registry.publishers["d1"] = Publisher(
        key="p1",
        name="University of Idaho William F Barr Entomological Museum",
        country="US",
        homepage="https://www.uidaho.edu/",
    )

    result = resolver(registry).resolve(
        record("UI", dataset_key="d1", publisher="University of Idaho William F Barr ...")
    )

    assert result.name == "University of Idaho William F Barr Entomological Museum"
    assert result.homepage == "https://www.uidaho.edu/"
    assert result.source is MatchSource.GBIF_PUBLISHER


def test_candidate_agreeing_with_publisher_is_verified(registry) -> None:
    registry.by_code["CSU"] = [
        RegistryInstitution(key="uco", code="CSU", name="University of Central Oklahoma"),
        RegistryInstitution(key="csu", code="CSU", name="Colorado State University"),
    ]
    result = resolver(registry).resolve(
        record("CSU", publisher="Colorado State University, C.P. Gillette Museum")
    )
    assert result.grscicoll_key == "csu"
    assert result.source is MatchSource.GRSCICOLL_VERIFIED


def test_unrelated_candidate_and_publisher_leave_code_unresolved(registry) -> None:
    registry.by_code["TU"] = [RegistryInstitution(key="t", code="TU", name="Temple University")]
    result = resolver(registry).resolve(
        record("TU", dataset_key="d1", publisher="University of Tartu, Natural History Museum")
    )
    assert result.name is None
    assert result.source is MatchSource.UNRESOLVED
    assert not result.retry


def test_aggregator_publisher_falls_back_to_country(registry) -> None:
    """A portal publishing many codes says nothing by its name."""
    registry.by_code["MZH"] = [
        RegistryInstitution(key="mzh", code="MZH", name="Helsinki Zoological Museum", country="FI"),
        RegistryInstitution(key="x", code="MZH", name="Elsewhere", country="SE"),
    ]
    portal = {"publisher": "Finnish Biodiversity Information Facility", "publishing_country": "FI"}

    results = resolver(registry).resolve_all([record("MZH", **portal), record("KUO", **portal)])

    assert results["MZH"].grscicoll_key == "mzh"
    assert results["KUO"].name is None


def test_country_is_not_evidence_for_a_single_code_publisher(registry) -> None:
    registry.by_code["MZH"] = [
        RegistryInstitution(key="mzh", code="MZH", name="Helsinki Zoological Museum", country="FI")
    ]
    result = resolver(registry).resolve(
        record("MZH", publisher="Some Finnish Society", publishing_country="FI")
    )
    assert result.name is None


def test_grscicoll_homepage_gap_filled_from_matching_publisher(registry) -> None:
    registry.by_code["DCH"] = [RegistryInstitution(key="dch", code="DCH", name="Davidson College")]
    registry.publishers["d1"] = Publisher(
        key="p", name="Davidson College", homepage="https://www.davidson.edu/"
    )
    result = resolver(registry).resolve(
        record("DCH", dataset_key="d1", publisher="Davidson College")
    )
    assert result.homepage == "https://www.davidson.edu/"


def test_most_common_dataset_is_tried_first(registry) -> None:
    registry.by_code["USNM"] = [
        RegistryInstitution(key="nmnh", code="USNM", name="National Museum of Natural History")
    ]
    registry.lookups[("USNM", "big")] = LookupResult(LookupMatch.EXACT, "nmnh")

    result = resolver(registry).resolve_all(
        [
            record("USNM", dataset_key="small", occurrences=1),
            record("USNM", dataset_key="big", occurrences=500),
        ]
    )["USNM"]

    assert result.source is MatchSource.GRSCICOLL_EXACT
    assert registry.calls[0] == ("lookup", "USNM", "big")


def test_verbatim_name_skips_the_registry(registry) -> None:
    result = resolver(registry).resolve(record("Universitas Cenderawasih (UNCEN)"))
    assert result.name == "Universitas Cenderawasih"
    assert result.source is MatchSource.VERBATIM
    assert registry.calls == []


def test_curated_name_wins_and_can_borrow_publisher_homepage(registry) -> None:
    registry.publishers["d1"] = Publisher(
        key="p", name="A.J. Cook Arthropod Research Collection", homepage="https://msu.example/"
    )
    overrides = {"MSU": Override(name="A.J. Cook Collection, MSU", use_publisher=True)}

    result = resolver(registry, overrides).resolve(record("MSU", dataset_key="d1"))

    assert result.name == "A.J. Cook Collection, MSU"
    assert result.homepage == "https://msu.example/"
    assert result.source is MatchSource.CURATED


def test_registry_failure_is_marked_for_retry(registry) -> None:
    registry.failing = True
    result = resolver(registry).resolve(record("MCZ", dataset_key="d1"))
    assert result.name is None
    assert result.retry


def test_placeholder_codes_are_skipped(registry) -> None:
    assert resolver(registry).resolve_all([record("-"), record("  ")]) == {}


def test_fingerprint_tracks_overrides(registry) -> None:
    plain = resolver(registry).fingerprint
    curated = resolver(registry, {"X": Override(name="Somewhere")}).fingerprint
    assert plain != curated
