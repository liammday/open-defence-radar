"""Eval-time groundedness: entailment judging of each cited claim."""

from __future__ import annotations

from odr.eval.groundedness import score_groundedness
from odr.eval.judge import FakeJudge
from odr.types import Answer, GroundednessReport, ScoredChunk


def _passage(cid: str, text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=cid, document_id=cid, title="t", text=text, score=0.9, source_name="s", url="u"
    )


def _answer(text: str, passages: list[ScoredChunk]) -> Answer:
    return Answer(
        text=text, citations=(), groundedness=GroundednessReport(0, 0, 0), retrieved=tuple(passages)
    )


def test_score_groundedness_judges_each_cited_claim() -> None:
    passages = [_passage("c1", "passage one"), _passage("c2", "passage two")]
    answer = _answer("Claim A [1]. Claim B [2].", passages)
    # judge entails only the claim citing passage one
    judge = FakeJudge(lambda claim, passage: passage == "passage one")
    report = score_groundedness(answer, judge)
    assert report.total_claims == 2
    assert report.supported == 1
    assert report.unsupported == 1
    assert report.score == 0.5


def test_uncited_claim_is_unsupported() -> None:
    passages = [_passage("c1", "passage one")]
    answer = _answer("A cited claim [1]. An uncited claim.", passages)
    report = score_groundedness(answer, FakeJudge(lambda c, p: True))
    assert report.total_claims == 2
    assert report.supported == 1  # the uncited sentence cannot be entailment-checked


def test_hallucinated_marker_is_unsupported() -> None:
    passages = [_passage("c1", "only passage")]
    answer = _answer("Claim citing a missing passage [9].", passages)
    report = score_groundedness(answer, FakeJudge(lambda c, p: True))
    assert report.supported == 0
