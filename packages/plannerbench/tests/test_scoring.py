from __future__ import annotations

from plannerbench.cases import Case
from plannerbench.scoring import (
    RawToolCall,
    Trial,
    grade,
    matches_plan,
    plan_signature,
    summarize,
    validate_calls,
)


def raw(name: str | None, arguments: str | None) -> RawToolCall:
    return RawToolCall(name=name, arguments=arguments)


def test_validation_mirrors_backend_acceptance_rules(spec) -> None:
    records = validate_calls(
        [
            raw("search_by_location", '{"location": " br "}'),
            raw("search_by_location", '{"location": "PE"}'),
            raw("search_by_weather", "{}"),
            raw("search_by_color", "not json"),
            raw("search_by_image_similarity", '["Danaus"]'),
            raw("search_by_traits", '{"canopy_affinity": null}'),
        ],
        spec,
    )

    assert [(r.name, r.valid, r.error) for r in records] == [
        ("search_by_location", True, None),
        ("search_by_location", False, "duplicate tool call"),
        ("search_by_weather", False, "unknown tool"),
        ("search_by_color", False, "arguments are not valid JSON"),
        ("search_by_image_similarity", False, "arguments are not a JSON object"),
        ("search_by_traits", False, records[5].error),
    ]
    # Whitespace is trimmed as the pydantic models do; an all-null trait call
    # is empty once nulls are dropped, which TraitArgs rejects.
    assert records[0].arguments == {"location": "br"}
    assert records[5].error is not None


def test_schema_violations_are_invalid(spec) -> None:
    records = validate_calls(
        [
            raw("search_by_location", '{"location": "Brazil"}'),
            raw("search_by_traits", '{"canopy_affinity": "Very high"}'),
            raw("search_by_color", '{"color_description": "blue", "extra": 1}'),
        ],
        spec,
    )
    assert [r.valid for r in records] == [False, False, False]


def test_plan_matching_is_exact_on_tools_and_flexible_on_values(spec) -> None:
    calls = validate_calls(
        [
            raw("search_by_color", '{"color_description": "blue"}'),
            raw("search_by_location", '{"location": "br"}'),
        ],
        spec,
    )
    assert matches_plan(calls, {"search_by_color": {}, "search_by_location": {"location": "BR"}})
    assert matches_plan(
        calls,
        {
            "search_by_color": {"color_description": "*"},
            "search_by_location": {"location": ["PE", "BR"]},
        },
    )
    # Missing and extra tools are both wrong.
    assert not matches_plan(calls, {"search_by_color": {}})
    assert not matches_plan(
        calls,
        {"search_by_color": {}, "search_by_location": {}, "search_by_traits": {}},
    )
    assert not matches_plan(
        calls, {"search_by_color": {}, "search_by_location": {"location": "PE"}}
    )


def test_empty_plan_accepts_only_no_tool(spec) -> None:
    case = Case(id="noop", query="hello", accept=[{}])
    assert grade(case, [])
    assert not grade(
        case, validate_calls([raw("search_by_color", '{"color_description": "x"}')], spec)
    )


def test_signature_ignores_order_and_case(spec) -> None:
    first = validate_calls(
        [
            raw("search_by_color", '{"color_description": "Blue"}'),
            raw("search_by_location", '{"location": "BR"}'),
        ],
        spec,
    )
    second = validate_calls(
        [
            raw("search_by_location", '{"location": "br"}'),
            raw("search_by_color", '{"color_description": "blue"}'),
        ],
        spec,
    )
    assert plan_signature(first) == plan_signature(second)


def _trial(model: str, case_id: str, repeat: int, **fields) -> Trial:
    return Trial(model=model, case_id=case_id, repeat=repeat, **fields)


def test_summary_counts_errors_as_misses_and_tracks_consistency() -> None:
    cases = [Case(id="a", query="a", accept=[{}]), Case(id="b", query="b", accept=[{}])]
    trials = [
        _trial(
            "m1",
            "a",
            1,
            status="ok",
            signature="x",
            correct=True,
            latency_seconds=1.0,
            prompt_tokens=100,
            completion_tokens=10,
            total_tokens=110,
        ),
        _trial(
            "m1",
            "a",
            2,
            status="ok",
            signature="x",
            correct=True,
            latency_seconds=3.0,
            prompt_tokens=100,
            completion_tokens=11,
            total_tokens=111,
        ),
        _trial(
            "m1",
            "b",
            1,
            status="ok",
            signature="x",
            correct=True,
            latency_seconds=2.0,
            prompt_tokens=100,
            completion_tokens=12,
            total_tokens=112,
        ),
        _trial("m1", "b", 2, status="error", error="Timeout"),
        _trial("m2", "a", 1, status="ok", signature="x", correct=True, latency_seconds=1.0),
        _trial("m2", "a", 2, status="ok", signature="y", correct=False, latency_seconds=1.0),
    ]

    m1, m2, m3 = summarize(trials, ["m1", "m2", "m3"], cases)

    assert (m1.correct, m1.trials, m1.api_errors, m1.accuracy) == (3, 4, 1, 0.75)
    assert m1.consistent_cases == 1  # case b had an error
    assert (m1.latency_p50_seconds, m1.latency_max_seconds) == (2.0, 3.0)
    assert (m1.prompt_tokens, m1.completion_tokens, m1.total_tokens) == (300, 33, 333)
    assert m1.per_case_correct == {"a": 2, "b": 1}
    assert m2.consistent_cases == 0  # different plans across repeats
    assert m3.trials == 0 and m3.accuracy == 0.0
