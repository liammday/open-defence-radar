"""Eval-time groundedness — judge whether each cited claim is entailed.

A claim sentence counts as supported only if it carries a [n] marker that
resolves to a real retrieved passage AND the judge finds that passage entails it.
"""

from __future__ import annotations

import re

from odr.eval.judge import Judge
from odr.types import Answer, GroundednessReport

_MARKER = re.compile(r"\[(\d+)\]")


def score_groundedness(answer: Answer, judge: Judge) -> GroundednessReport:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.text) if s.strip()]
    claims = [s for s in sentences if any(c.isalpha() for c in s)]
    supported = 0
    for claim in claims:
        valid = [
            n for n in (int(m) for m in _MARKER.findall(claim)) if 1 <= n <= len(answer.retrieved)
        ]
        if valid and any(judge.judge(claim, answer.retrieved[n - 1].text) for n in valid):
            supported += 1
    total = len(claims)
    return GroundednessReport(
        total_claims=total, supported=supported, unsupported=total - supported
    )
