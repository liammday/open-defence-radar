"""Trust dashboard view-model — assemble the gauges from the eval artifacts.

Reads `data/eval/latest.json` (the artifact the eval runner writes) plus the
threshold floors/ceiling, and computes per-metric pass/warn state and the gauge
geometry the template renders. Returns ``None`` when no eval has run yet, so the
dashboard can show a graceful "run the eval" state instead of inventing numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# (json key, display label, sub-detail, inverted?, gauge fill class, plain-English caption)
_METRICS: tuple[tuple[str, str, str, bool, str, str], ...] = (
    (
        "hit_rate",
        "Retrieval hit-rate",
        "recall@k",
        False,
        "signal",
        "Of the evaluation questions, how often the right source was "
        "retrieved into the top results.",
    ),
    (
        "groundedness",
        "Groundedness",
        "entailment-judged",
        False,
        "good",
        "How often the answer's claims are supported by a retrieved passage, "
        "checked independently.",
    ),
    (
        "unsupported_claim_rate",
        "Unsupported-claim",
        "lower is better",
        True,
        "good",
        "Share of claims with no supporting passage — the inverse of "
        "groundedness; lower is better.",
    ),
)


@dataclass(frozen=True)
class MetricView:
    """One gauge: a value measured against a floor (or ceiling, when inverted)."""

    key: str
    label: str
    value: float
    bound: float  # floor for normal metrics; ceiling when inverted
    inverted: bool  # unsupported-claim: lower is better
    passed: bool
    fill_class: str  # "signal" | "good"
    detail: str
    explanation: str  # plain-English caption for observers
    history: tuple[float, ...]

    @property
    def value_display(self) -> str:
        return f"{self.value:.2f}"

    @property
    def bound_display(self) -> str:
        return f"{self.bound:g}"

    @property
    def sub(self) -> str:
        return f"{'ceiling' if self.inverted else 'floor'} {self.bound_display} · {self.detail}"

    @property
    def status(self) -> str:
        return "pass" if self.passed else "warn"

    @property
    def right_pct(self) -> float:
        """Gauge `right` inset (%): the fill sweeps to cover `value` of the track."""
        return round((1.0 - _clamp01(self.value)) * 100, 1)

    @property
    def marker_pct(self) -> float:
        """Floor/ceiling marker position (%) along the track."""
        return round(_clamp01(self.bound) * 100, 1)

    @property
    def spark_vals(self) -> str:
        """Comma-joined history scaled to 0–100 for the sparkline bars."""
        return ",".join(f"{round(_clamp01(v) * 100, 1):g}" for v in self.history)


@dataclass(frozen=True)
class TrustView:
    generated_at: str
    question_count: int
    metrics: tuple[MetricView, ...]

    @property
    def all_passed(self) -> bool:
        return all(m.passed for m in self.metrics)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def load_trust_view(eval_dir: Path | str, thresholds: dict[str, float]) -> TrustView | None:
    """Build the dashboard view-model, or ``None`` if no eval artifact exists yet."""
    eval_dir = Path(eval_dir)
    latest = eval_dir / "latest.json"
    if not latest.exists():
        return None
    data = json.loads(latest.read_text(encoding="utf-8"))
    history = _load_history(eval_dir)

    metrics: list[MetricView] = []
    for key, label, detail, inverted, fill_class, explanation in _METRICS:
        value = float(data[key])
        bound = float(thresholds[key])
        passed = value <= bound if inverted else value >= bound
        series = tuple(history.get(key, ())) or (value,)
        metrics.append(
            MetricView(
                key=key,
                label=label,
                value=value,
                bound=bound,
                inverted=inverted,
                passed=passed,
                fill_class=fill_class,
                detail=detail,
                explanation=explanation,
                history=series,
            )
        )

    return TrustView(
        generated_at=str(data.get("generated_at", "")),
        question_count=int(data.get("question_count", 0)),
        metrics=tuple(metrics),
    )


def _load_history(eval_dir: Path, limit: int = 10) -> dict[str, list[float]]:
    """The last `limit` history snapshots, as per-metric value series (oldest→newest)."""
    hist_dir = eval_dir / "history"
    if not hist_dir.is_dir():
        return {}
    series: dict[str, list[float]] = {}
    for path in sorted(hist_dir.glob("*.json"))[-limit:]:
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key, *_ in _METRICS:
            if key in snapshot:
                series.setdefault(key, []).append(float(snapshot[key]))
    return series
