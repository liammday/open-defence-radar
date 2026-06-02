"""Orchestrator: run sub-questions through a query fn, recombine into one Brief."""

from __future__ import annotations

from datetime import date

from odr.agent.orchestrator import decompose_and_answer
from odr.agent.planner import FakePlanner
from odr.types import Answer, Citation, Filters, GroundednessReport, ScoredChunk


def _answer(text: str, cites: tuple[Citation, ...], n_retrieved: int) -> Answer:
    retrieved = tuple(
        ScoredChunk(f"c{i}", f"d{i}", "T", "…", 0.5, "Src", "https://x") for i in range(n_retrieved)
    )
    supported = len(cites)
    return Answer(
        text=text,
        citations=cites,
        groundedness=GroundednessReport(total_claims=supported, supported=supported, unsupported=0),
        retrieved=retrieved,
    )


def _cite(marker: str, url: str) -> Citation:
    return Citation(marker, "ch", "Title " + url, "Source", url, date(2026, 1, 1))


def test_recombines_renumbers_and_dedupes_citations() -> None:
    a1 = _answer("Contracts mention AI [1].", (_cite("[1]", "https://u/a"),), 2)
    a2 = _answer(
        "Tenders cite autonomy [1] and AI [2].",
        (_cite("[1]", "https://u/a"), _cite("[2]", "https://u/b")),  # [1] dupes a1's source
        2,
    )
    responses = {"q1": a1, "q2": a2}

    def query_fn(topic: str, k: int, filters: Filters | None) -> Answer:
        return responses[topic]

    brief = decompose_and_answer("hard q", planner=FakePlanner(["q1", "q2"]), query_fn=query_fn)

    assert brief.sub_questions == ("q1", "q2")
    # global citations: a's url -> [1], b's url -> [2]; a2's local [1] (a's url) deduped to [1]
    assert [c.marker for c in brief.citations] == ["[1]", "[2]"]
    assert [c.url for c in brief.citations] == ["https://u/a", "https://u/b"]
    # a2's text renumbered: local [1]->[1] (same url), local [2]->[2]
    assert "autonomy [1] and AI [2]" in brief.text
    assert brief.question in brief.text
    # aggregated groundedness: 1 + 2 = 3 supported / 3 total
    assert (brief.groundedness.supported, brief.groundedness.total_claims) == (3, 3)


def test_empty_sub_answer_renders_a_note_not_a_fabrication() -> None:
    empty = _answer("", (), 0)
    good = _answer("Found it [1].", (_cite("[1]", "https://u/a"),), 1)
    responses = {"empty": empty, "good": good}

    brief = decompose_and_answer(
        "q",
        planner=FakePlanner(["empty", "good"]),
        query_fn=lambda topic, k, filters: responses[topic],
    )
    assert "No grounded passages matched" in brief.text
    assert [c.marker for c in brief.citations] == ["[1]"]


def test_falls_back_to_source_split_when_planner_returns_nothing() -> None:
    calls: list[tuple[str, Filters | None]] = []

    def query_fn(topic: str, k: int, filters: Filters | None) -> Answer:
        calls.append((topic, filters))
        return _answer(f"Re {topic} [1].", (_cite("[1]", f"https://u/{len(calls)}"),), 1)

    brief = decompose_and_answer(
        "broad question",
        planner=FakePlanner([]),  # planner yields nothing -> fallback
        query_fn=query_fn,
        fallback_sources=("contracts-finder", "govuk-mod"),
    )

    # one call per fallback source, each filtered to that source, all with the original question
    assert [t for t, _ in calls] == ["broad question", "broad question"]
    assert [f.sources for _, f in calls if f] == [("contracts-finder",), ("govuk-mod",)]
    assert brief.sub_questions == ("From contracts-finder", "From govuk-mod")
    assert len(brief.citations) == 2  # distinct urls, not deduped
