"""Eval runner — score the fixture question set and write a JSON artifact.

Runs against the committed fixture corpus (seeded fresh), so results are
reproducible. Retrieval scoring is offline; groundedness uses the injected judge
(real one needs a key — inject a FakeJudge in tests).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from odr.embed.base import Embedder
from odr.eval.dataset import Question, load_questions, seed_store
from odr.eval.groundedness import score_groundedness
from odr.eval.judge import Judge
from odr.eval.scorers import score_retrieval
from odr.retrieve.retriever import Retriever
from odr.store.memory_store import InMemoryStore
from odr.synthesise.base import Generator
from odr.synthesise.synthesiser import Synthesiser
from odr.types import Document


@dataclass(frozen=True)
class EvalResult:
    hit_rate: float
    recall_at_k: float
    mrr: float
    groundedness: float
    unsupported_claim_rate: float
    question_count: int
    generated_at: str


def run_eval(
    embedder: Embedder,
    generator: Generator,
    judge: Judge,
    *,
    questions: list[Question] | None = None,
    corpus: list[Document] | None = None,
    k: int = 8,
) -> EvalResult:
    store = InMemoryStore()
    store.init_schema()
    seed_store(store, embedder, corpus)
    retriever = Retriever(store, embedder)
    synthesiser = Synthesiser(generator)

    items = questions if questions is not None else load_questions()
    pairs: list[tuple[tuple[str, ...], list[str]]] = []
    supported = total = 0
    for q in items:
        hits = retriever.retrieve(q.question, k=k, filters=q.filters)
        pairs.append((q.relevant_doc_ids, [h.document_id for h in hits]))
        report = score_groundedness(synthesiser.answer(q.question, hits), judge)
        supported += report.supported
        total += report.total_claims

    retrieval = score_retrieval(pairs)
    groundedness = round(supported / total if total else 1.0, 6)
    return EvalResult(
        hit_rate=round(retrieval.hit_rate, 6),
        recall_at_k=round(retrieval.recall_at_k, 6),
        mrr=round(retrieval.mrr, 6),
        groundedness=groundedness,
        unsupported_claim_rate=round(1.0 - groundedness, 6),
        question_count=len(items),
        generated_at=datetime.now(UTC).isoformat(),
    )


def load_thresholds() -> dict[str, float]:
    """The eval floors/ceiling (ignores `_`-prefixed annotation keys)."""
    path = Path(__file__).parent / "fixtures" / "thresholds.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in raw.items() if not k.startswith("_")}


def write_result(result: EvalResult, directory: Path) -> Path:
    """Write latest.json (+ a timestamped history copy); return the latest path."""
    directory = Path(directory)
    (directory / "history").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(result), indent=2)
    latest = directory / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    stamp = result.generated_at.replace(":", "").replace("-", "")
    (directory / "history" / f"{stamp}.json").write_text(payload, encoding="utf-8")
    return latest
