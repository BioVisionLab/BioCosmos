"""Parity between the backend's code descriptions and colharmonize's enums.

app.services.col_match_codes mirrors the prose rather than importing
colharmonize at runtime. These tests make that mirror a checked copy: if the
upstream enums gain a member or reword a description, this fails instead of the
API quietly serving stale text.
"""

import pytest

from app.services.col_match_codes import (
    MATCH_METHOD_DESCRIPTIONS,
    RANK_PREFIX_NOTES,
    UPDATE_STATUS_DESCRIPTIONS,
    all_descriptions,
    describe_match_method,
    describe_reason_code,
    describe_update_status,
    split_match_method,
)

colharmonize_models = pytest.importorskip(
    "colharmonize.models",
    reason="colharmonize is a workspace member; install with `uv sync --all-packages`",
)


class TestParityWithColharmonize:
    def test_update_status_members_match(self):
        upstream = {status.value for status in colharmonize_models.UpdateStatus}
        assert set(UPDATE_STATUS_DESCRIPTIONS) == upstream

    def test_update_status_prose_matches(self):
        for status in colharmonize_models.UpdateStatus:
            assert UPDATE_STATUS_DESCRIPTIONS[status.value] == status.description

    def test_match_method_members_match(self):
        upstream = {method.value for method in colharmonize_models.MatchMethod}
        assert set(MATCH_METHOD_DESCRIPTIONS) == upstream

    def test_match_method_prose_matches(self):
        for method in colharmonize_models.MatchMethod:
            assert MATCH_METHOD_DESCRIPTIONS[method.value] == method.description


class TestSplitMatchMethod:
    def test_unprefixed_method(self):
        assert split_match_method("EXACT_ACCEPTED") == (None, "EXACT_ACCEPTED")

    def test_genus_prefixed_method(self):
        assert split_match_method("GENUS_SPELLING_EPITHET") == (
            "GENUS",
            "SPELLING_EPITHET",
        )

    def test_subspecies_prefixed_method(self):
        assert split_match_method("SUBSPECIES_EXACT_SYNONYM") == (
            "SUBSPECIES",
            "EXACT_SYNONYM",
        )

    def test_spelling_genus_is_not_mistaken_for_a_prefix(self):
        # SPELLING_GENUS is a method in its own right, not GENUS-prefixed.
        assert split_match_method("SPELLING_GENUS") == (None, "SPELLING_GENUS")

    def test_genus_prefixed_spelling_genus(self):
        assert split_match_method("GENUS_SPELLING_GENUS") == ("GENUS", "SPELLING_GENUS")

    def test_unknown_code(self):
        assert split_match_method("WISHFUL_THINKING") == (None, None)

    def test_unknown_base_under_a_known_prefix(self):
        assert split_match_method("GENUS_NOT_A_METHOD") == (None, None)

    @pytest.mark.parametrize("code", ["", None])
    def test_empty_code(self, code):
        assert split_match_method(code) == (None, None)


class TestDescribe:
    def test_status_description(self):
        assert describe_update_status("MATCHED") == (
            "One accepted taxon was resolved with sufficient evidence."
        )

    def test_status_is_case_insensitive(self):
        assert describe_update_status("matched") == describe_update_status("MATCHED")

    def test_unknown_status_is_none(self):
        assert describe_update_status("PERHAPS") is None

    def test_method_description(self):
        assert (
            describe_match_method("EXACT_SYNONYM")
            == (MATCH_METHOD_DESCRIPTIONS["EXACT_SYNONYM"])
        )

    def test_prefixed_method_leads_with_the_cascade_note(self):
        described = describe_match_method("GENUS_SPELLING_EPITHET")
        assert described is not None
        assert described.startswith(RANK_PREFIX_NOTES["GENUS"])
        assert described.endswith(MATCH_METHOD_DESCRIPTIONS["SPELLING_EPITHET"])

    def test_unknown_method_is_none(self):
        # The UI renders a plain label rather than an empty hint panel.
        assert describe_match_method("MADE_UP") is None

    def test_reason_codes(self):
        assert describe_reason_code("UNSUPPORTED_RANK") is not None
        assert describe_reason_code("INVALID_BINOMIAL") is not None
        assert describe_reason_code("NO_SUCH_REASON") is None


class TestAllDescriptions:
    def test_shape(self):
        payload = all_descriptions()
        assert set(payload) == {"updateStatus", "matchMethod", "reasonCode"}

    def test_includes_every_prefixed_method(self):
        methods = all_descriptions()["matchMethod"]
        expected = len(MATCH_METHOD_DESCRIPTIONS) * (1 + len(RANK_PREFIX_NOTES))
        assert len(methods) == expected
        assert "GENUS_FUZZY_TYPO" in methods
        assert "SUBSPECIES_EXACT_ACCEPTED" in methods

    def test_prefixed_entries_agree_with_describe(self):
        methods = all_descriptions()["matchMethod"]
        for code, description in methods.items():
            assert describe_match_method(code) == description

    def test_returns_a_copy(self):
        payload = all_descriptions()
        payload["updateStatus"]["MATCHED"] = "tampered"
        assert UPDATE_STATUS_DESCRIPTIONS["MATCHED"] != "tampered"
