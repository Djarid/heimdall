"""The false-inert catch: Fenrir + Huginn as D67-fix direction (d).

This is the payoff of the Phase 2 detection layer and the reason it was built now
(decision D74). The deterministic classifier (Nornir) has a measured false-inert
residual: consequential content that positively earns an inert signal (`fi-19` a
passively-phrased standing order, `fi-20` a metaphor) is typed inert and skips both the
gate and human review. No content pattern closes this without world knowledge, which
invariant 3.1 keeps off the classification path (D72).

The attempt-introspection catch attacks it from a different axis. It does not classify
the content; it observes what a model DOES when it reads the content. Route the same
adversarial corpus through Fenrir under Huginn's tripwire: a model steered by a
consequential payload emits an action-shaped intermediate (a request to act, which
Fenrir's empty capability set refuses), and that attempt is dispositive proof the
content was consequential, so it is quarantined to review. Because behaviour is harder
to phrase passively than surface text is, this catches cases the content classifier
misses.

This module measures the catch over the corpus. It is a fail-closed detector: a hit
quarantines, never grants inertness (invariant 3.5). It reduces but does not close the
gap, and the measurement reports both what it catches and what it still misses (the
honest residual, fenrir.md section 9), rather than a hollow green.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .fenrir import EmissionProducer, extract
from .huginn import monitor


CORPUS = (
    Path(__file__).resolve().parents[1]
    / "ontology" / "tests" / "corpora" / "false_inert_adversarial.json"
)


@dataclass
class CatchResult:
    case_id: str
    ground_truth: str            # 'consequential' or 'benign'
    caught: bool                 # did the tripwire fire (attempt introspection)?
    quarantined: bool            # did Huginn halt and route to review?


@dataclass
class CatchReport:
    results: list[CatchResult]

    @property
    def consequential(self) -> list[CatchResult]:
        return [r for r in self.results if r.ground_truth == "consequential"]

    @property
    def benign(self) -> list[CatchResult]:
        return [r for r in self.results if r.ground_truth != "consequential"]

    @property
    def caught_consequential(self) -> list[CatchResult]:
        return [r for r in self.consequential if r.caught]

    @property
    def missed_consequential(self) -> list[CatchResult]:
        return [r for r in self.consequential if not r.caught]

    @property
    def false_catches(self) -> list[CatchResult]:
        """Benign cases the tripwire wrongly flagged. Must be empty: the zero-false-
        positive property is the whole basis of the tripwire being dispositive."""
        return [r for r in self.benign if r.caught]


def _content_of(fields: dict) -> str:
    """Reconstruct the tainted content window a model would read from the corpus
    fields, the same shape the classifier's `text_of` uses."""
    parts = [str(v) for v in fields.values() if v]
    return " ".join(parts)


def run_catch(producer: EmissionProducer) -> CatchReport:
    """Route every corpus case through Fenrir + Huginn under the given producer and
    record, per case, whether the attempt-introspection tripwire fired."""
    data = json.loads(CORPUS.read_text())
    results: list[CatchResult] = []
    for case in data["cases"]:
        content = _content_of(case["fields"])
        run = extract(content, producer)
        result = monitor(run)
        results.append(
            CatchResult(
                case_id=case["id"],
                ground_truth=case["ground_truth"],
                caught=result.consequential_catch,
                quarantined=result.quarantined,
            )
        )
    return CatchReport(results=results)
