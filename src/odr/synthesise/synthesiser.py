"""Grounded synthesis — answer only from retrieved passages, every claim cited.

Synthesis-time groundedness (cheap, every query): each factual sentence must
carry a [n] marker that resolves to a *real* retrieved passage. Entailment-level
groundedness (does the cited passage actually support the claim?) is the
eval-time check added in Phase 2 (#2-range).
"""

from __future__ import annotations

import re

from odr.synthesise.base import Generator
from odr.types import Answer, Citation, GroundednessReport, ScoredChunk

_SYSTEM = (
    "You are a careful analyst. Answer the question using ONLY the numbered passages "
    "provided. Every factual claim MUST cite its supporting passage with a marker like "
    "[1] or [2]. If the passages do not support an answer, say so plainly. Do not use "
    "outside knowledge. Be concise."
)
_MARKER = re.compile(r"\[(\d+)\]")
_NO_PASSAGES = "No grounded passages matched this query."


class Synthesiser:
    def __init__(self, generator: Generator) -> None:
        self._generator = generator

    def answer(self, query: str, passages: list[ScoredChunk]) -> Answer:
        if not passages:
            return Answer(
                text=_NO_PASSAGES,
                citations=(),
                groundedness=GroundednessReport(0, 0, 0),
                retrieved=(),
            )
        text = self._generator.generate(_SYSTEM, self._build_prompt(query, passages)).strip()
        return Answer(
            text=text,
            citations=tuple(self._citations(text, passages)),
            groundedness=self._groundedness(text, len(passages)),
            retrieved=tuple(passages),
        )

    @staticmethod
    def _build_prompt(query: str, passages: list[ScoredChunk]) -> str:
        lines = [f"Question: {query}", "", "Passages:"]
        for i, p in enumerate(passages, start=1):
            published = p.published_at.isoformat() if p.published_at else None
            meta = " · ".join(part for part in (p.source_name, published, p.title) if part)
            lines.append(f"[{i}] ({meta})\n{p.text}")
        lines += ["", "Answer the question, citing supporting passages with [n]."]
        return "\n".join(lines)

    @staticmethod
    def _citations(text: str, passages: list[ScoredChunk]) -> list[Citation]:
        out: list[Citation] = []
        for n in sorted({int(m) for m in _MARKER.findall(text)}):
            if 1 <= n <= len(passages):
                p = passages[n - 1]
                out.append(
                    Citation(
                        marker=f"[{n}]",
                        chunk_id=p.chunk_id,
                        document_title=p.title,
                        source_name=p.source_name,
                        url=p.url,
                        published_at=p.published_at,
                    )
                )
        return out

    @staticmethod
    def _groundedness(text: str, n_passages: int) -> GroundednessReport:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        claims = [s for s in sentences if any(ch.isalpha() for ch in s)]
        supported = sum(
            1 for s in claims if any(1 <= int(m) <= n_passages for m in _MARKER.findall(s))
        )
        return GroundednessReport(
            total_claims=len(claims), supported=supported, unsupported=len(claims) - supported
        )
