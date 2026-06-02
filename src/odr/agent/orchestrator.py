"""Decompose a question into sub-queries, run each grounded query, recombine.

Recombination is structured and deterministic (no extra synthesis call): citation
markers are renumbered into one global, URL-deduped list; sub-answers with nothing
grounded render a note rather than a fabrication; groundedness is summed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from odr.agent.planner import Planner
from odr.query import answer_query
from odr.types import Answer, Brief, Citation, Filters, GroundednessReport

QueryFn = Callable[[str, int, Filters | None], Answer]

_DEFAULT_SOURCES: tuple[str, ...] = ("contracts-finder", "find-a-tender", "govuk-mod")


def _renumber(text: str, local_to_global: dict[str, str]) -> str:
    return re.sub(r"\[\d+\]", lambda m: local_to_global.get(m.group(0), m.group(0)), text)


def decompose_and_answer(
    question: str,
    *,
    planner: Planner,
    query_fn: QueryFn = answer_query,
    k: int = 8,
    fallback_sources: Sequence[str] = _DEFAULT_SOURCES,
) -> Brief:
    subs = planner.plan(question)
    if subs:
        runs: list[tuple[str, Answer]] = [(sub, query_fn(sub, k, None)) for sub in subs]
    else:  # deterministic source-split fallback
        runs = [
            (f"From {src}", query_fn(question, k, Filters(sources=(src,))))
            for src in fallback_sources
        ]

    global_cites: list[Citation] = []
    by_url: dict[str, str] = {}
    sections: list[str] = []
    supported = total = 0

    for label, ans in runs:
        local_to_global: dict[str, str] = {}
        for c in ans.citations:
            marker = by_url.get(c.url)
            if marker is None:
                marker = f"[{len(global_cites) + 1}]"
                by_url[c.url] = marker
                global_cites.append(
                    Citation(
                        marker=marker,
                        chunk_id=c.chunk_id,
                        document_title=c.document_title,
                        source_name=c.source_name,
                        url=c.url,
                        published_at=c.published_at,
                    )
                )
            local_to_global[c.marker] = marker
        grounded = bool(ans.citations or ans.retrieved)
        body = _renumber(ans.text, local_to_global) if grounded else "No grounded passages matched."
        sections.append(f"## {label}\n{body}")
        supported += ans.groundedness.supported
        total += ans.groundedness.total_claims

    text = f"In response to: {question}\n\n" + "\n\n".join(sections)
    return Brief(
        question=question,
        sub_questions=tuple(label for label, _ in runs),
        text=text,
        citations=tuple(global_cites),
        groundedness=GroundednessReport(
            total_claims=total, supported=supported, unsupported=total - supported
        ),
    )
