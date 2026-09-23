from __future__ import annotations

import pytest

from instharmonize.names import (
    code_matches_name,
    is_placeholder_code,
    name_similarity,
    split_verbatim_name,
)


def test_names_differing_by_a_qualifier_agree() -> None:
    assert name_similarity("Natural History Museum", "Natural History Museum, London") == 1.0
    assert (
        name_similarity(
            "Museum of Comparative Zoology, Harvard University",
            "Harvard University, Museum of Comparative Zoology",
        )
        == 1.0
    )


def test_one_shared_generic_word_is_not_agreement() -> None:
    assert name_similarity("King Saud University", "Kansas State University Museum") == 0.0


def test_accents_and_case_are_ignored() -> None:
    assert name_similarity("Museo de Zoología", "MUSEO DE ZOOLOGIA") == 1.0


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("KSU", "Kansas State University Museum of Entomological and Prairie Arthropod Research"),
        ("UI", "University of Idaho William F Barr Entomological Museum"),
        ("ASU", "Arizona State University Biocollections"),
        ("WWU", "Western Washington University Insect Collection (WWUC)"),
        ("UMNH", "Natural History Museum of Utah (UMNH)"),
    ],
)
def test_code_spelled_out_by_name(code: str, name: str) -> None:
    assert code_matches_name(code, name)


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("NHMUK", "Natural History Museum"),
        ("MZH", "Finnish Biodiversity Information Facility"),
        ("TU", "University of Tartu, Natural History Museum and Botanical Garden"),
        # The first significant word has to start the code.
        ("UI", "Museum of the University of Iowa"),
        ("X", "Xylarium"),
    ],
)
def test_code_not_spelled_out_by_name(code: str, name: str) -> None:
    assert not code_matches_name(code, name)


def test_full_name_in_code_field() -> None:
    assert split_verbatim_name("Hartland Nature Club") == ("Hartland Nature Club", None)
    assert split_verbatim_name("Universitas Cenderawasih (UNCEN)") == (
        "Universitas Cenderawasih",
        "UNCEN",
    )


@pytest.mark.parametrize("code", ["MCZ", "SMNH-NASU", "tesri", "MST-and-NHMD", "SLU ARTDATABANKEN"])
def test_codes_are_not_names(code: str) -> None:
    assert split_verbatim_name(code) is None


@pytest.mark.parametrize("code", [None, "", " ", "-", "NA", "Unknown"])
def test_placeholder_codes(code: str | None) -> None:
    assert is_placeholder_code(code)
