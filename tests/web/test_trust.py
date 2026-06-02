"""Trust dashboard view-model: load eval JSON + thresholds, compute pass/warn."""

from __future__ import annotations

import json
from pathlib import Path

from odr.web.trust import load_trust_view

_THRESHOLDS = {"hit_rate": 0.8, "groundedness": 0.9, "unsupported_claim_rate": 0.1}


def _write_latest(eval_dir: Path, **overrides: float) -> None:
    eval_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "hit_rate": 0.92,
        "recall_at_k": 0.9,
        "mrr": 0.85,
        "groundedness": 0.97,
        "unsupported_claim_rate": 0.03,
        "question_count": 24,
        "generated_at": "2026-06-02T09:00:00+00:00",
    }
    payload.update(overrides)
    (eval_dir / "latest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_trust_view_none_when_no_eval(tmp_path: Path) -> None:
    assert load_trust_view(tmp_path, _THRESHOLDS) is None


def test_load_trust_view_all_pass(tmp_path: Path) -> None:
    _write_latest(tmp_path)
    view = load_trust_view(tmp_path, _THRESHOLDS)
    assert view is not None
    assert view.question_count == 24
    assert view.all_passed is True

    by_key = {m.key: m for m in view.metrics}
    assert by_key["hit_rate"].value == 0.92
    assert by_key["hit_rate"].passed is True
    assert by_key["hit_rate"].value_display == "0.92"
    assert by_key["hit_rate"].right_pct == 8.0  # gauge fills to value (right = 100 - value%)
    assert by_key["unsupported_claim_rate"].inverted is True
    assert by_key["unsupported_claim_rate"].passed is True  # 0.03 <= ceiling 0.10


def test_load_trust_view_flags_hit_rate_breach(tmp_path: Path) -> None:
    _write_latest(tmp_path, hit_rate=0.5)
    view = load_trust_view(tmp_path, _THRESHOLDS)
    assert view is not None
    assert {m.key: m.passed for m in view.metrics}["hit_rate"] is False
    assert view.all_passed is False


def test_load_trust_view_flags_unsupported_breach(tmp_path: Path) -> None:
    _write_latest(tmp_path, unsupported_claim_rate=0.2)  # above ceiling 0.10
    view = load_trust_view(tmp_path, _THRESHOLDS)
    assert view is not None
    assert {m.key: m.passed for m in view.metrics}["unsupported_claim_rate"] is False
    assert view.all_passed is False
