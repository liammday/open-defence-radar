"""Grounded synthesiser: citation extraction + synthesis-time groundedness.

Uses FakeGenerator (a scripted answer) so the grounding logic is tested without
a real model call. The live AnthropicGenerator is exercised manually with a key.
"""

from __future__ import annotations

from datetime import date

from odr.synthesise.anthropic_generator import AnthropicGenerator
from odr.synthesise.base import Generator
from odr.synthesise.fake_generator import FakeGenerator
from odr.synthesise.synthesiser import Synthesiser
from odr.types import ScoredChunk


def _passage(cid: str, title: str, text: str, published: date | None = None) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=cid,
        document_id=f"doc-{cid}",
        title=title,
        text=text,
        score=0.9,
        source_name="Contracts Finder",
        url=f"https://example.gov.uk/{cid}",
        published_at=published,
    )


def _requires_generator(_g: Generator) -> None:
    """No-op whose signature makes mypy enforce Generator conformance."""


class _BoomGenerator:
    model_id = "boom"

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        raise AssertionError("generator must not be called when there are no passages")


def test_generators_conform_to_protocol() -> None:
    _requires_generator(FakeGenerator("x"))
    _requires_generator(AnthropicGenerator())  # cheap: client/SDK load lazily, no key needed


def test_no_passages_short_circuits_without_calling_generator() -> None:
    answer = Synthesiser(_BoomGenerator()).answer("anything", [])
    assert answer.citations == ()
    assert answer.groundedness.total_claims == 0
    assert answer.retrieved == ()
    assert answer.text  # a clear "no grounded passages" message


def test_extracts_citations_and_full_groundedness() -> None:
    passages = [
        _passage("c1", "Doc One", "AI tooling", published=date(2026, 1, 1)),
        _passage("c2", "Doc Two", "autonomy"),
    ]
    gen = FakeGenerator("The MoD bought AI tooling [1]. It also covers autonomy [2].")
    answer = Synthesiser(gen).answer("what?", passages)
    assert len(answer.citations) == 2
    assert answer.citations[0].marker == "[1]"
    assert answer.citations[0].chunk_id == "c1"
    assert answer.citations[0].document_title == "Doc One"
    assert answer.groundedness.total_claims == 2
    assert answer.groundedness.supported == 2
    assert answer.groundedness.score == 1.0
    assert len(answer.retrieved) == 2


def test_unsupported_claim_is_counted() -> None:
    passages = [_passage("c1", "Doc", "the source fact")]
    gen = FakeGenerator("Supported fact [1]. Unsupported claim with no marker.")
    answer = Synthesiser(gen).answer("q", passages)
    assert answer.groundedness.total_claims == 2
    assert answer.groundedness.supported == 1
    assert answer.groundedness.unsupported == 1


def test_hallucinated_citation_is_not_resolved() -> None:
    passages = [_passage("c1", "Doc", "the only passage")]
    gen = FakeGenerator("A claim citing a passage that was never retrieved [5].")
    answer = Synthesiser(gen).answer("q", passages)
    assert answer.citations == ()  # [5] resolves to no real passage
    assert answer.groundedness.supported == 0
    assert answer.groundedness.unsupported == 1
