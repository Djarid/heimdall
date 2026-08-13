"""Nornir's four rule kinds, authored as deterministic data-plus-checks.

No model authors or runs these (invariant 3.1). Each rule is human-authored, plain
Python, versioned and reviewed as trust-boundary code (`ONTOLOGY_CONSTRUCTION.md`
section 6). The four kinds:

1. Classification rules map a marshalled assertion to its ontology type. No match
   means the fail-safe (UNCLASSIFIED), never a guess.
2. Derivation rules forward-chain facts after classification; each derived fact
   carries its assertion chain.
3. Constraint axioms state what must not hold; a violation is a Gjallarhorn event.
4. Flow-to-sink propagation assigns action-critical status transitively, reproducing
   the algorithm the substrate spike proved (D43, D44).

A note on classification and injection. A classification rule reads the extracted
fields to decide a type. This is describing untrusted content, not obeying it (the
PoC's describe-vs-obey distinction). The rules match on the SHAPE and KEYWORDS of
the extracted values deterministically; they cannot be told to "reclassify" by the
content, because they are fixed Python, not an instruction-follower. The adversarial
test (obligation 8.2) is precisely whether a crafted payload can drive a
misclassification that downgrades an action-critical value; the rules are written to
be conservative (when in doubt, the higher-risk type or the fail-safe), because a
downgrade is a critical finding and an over-classification to a high-risk type only
costs a human review.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .assertions import ClassifiedAssertion, MarshalledAssertion


# --- 1. Classification rules ---------------------------------------------------

@dataclass(frozen=True)
class ClassificationRule:
    """A named, ordered classification rule. `test` returns True if the assertion is
    of `type_name`. Rules are tried in order; the first match wins, so more specific
    and higher-risk rules come first. `version` tracks the rule as code."""

    name: str
    type_name: str
    test: Callable[[MarshalledAssertion], bool]
    version: str = "1"


def _text(a: MarshalledAssertion) -> str:
    """The concatenated extracted text the rules match against, lower-cased. Reading
    it is describing untrusted content, not obeying it."""
    parts = []
    for key in ("subject_extracted", "requested_action_summary"):
        v = a.fields.get(key)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


# Keyword sets for the high-risk requested-action subtypes. Deliberately broad: an
# over-match costs a human review, an under-match risks a downgrade (a critical
# finding), so the rules err toward the higher-risk type.
_PAYMENT = re.compile(
    r"\b(payment|invoice|wire|transfer|remit|pay|bank details|account number|"
    r"iban|swift|sort code|settle|outstanding balance|purchase order)\b"
)
_INSTRUCTION = re.compile(
    r"\b(run|execute|install|configure|change the|update the|forward|delete|"
    r"disable|grant|approve|click|download|open the attachment|reset|deploy)\b"
)
_CREDENTIAL = re.compile(
    r"\b(password|passphrase|credential|mfa|2fa|one-time code|otp|verification code|"
    r"token|api key|access code|log ?in to|sign in to|authenticate)\b"
)


def _is_payment(a: MarshalledAssertion) -> bool:
    return bool(_PAYMENT.search(_text(a)))


def _is_instruction(a: MarshalledAssertion) -> bool:
    return bool(_INSTRUCTION.search(_text(a)))


def _is_credential(a: MarshalledAssertion) -> bool:
    return bool(_CREDENTIAL.search(_text(a)))


def _is_communication(a: MarshalledAssertion) -> bool:
    """Anything with a sender or subject is at least a communication. This is the
    broad catch that keeps genuine messages inside the domain rather than falling to
    the fail-safe; the fail-safe is for content that is not recognisably a
    communication at all."""
    return bool(a.fields.get("sender_extracted") or a.fields.get("subject_extracted"))


# Ordered: high-risk subtypes first, then the informational default, then the bare
# communication, then (implicitly) the fail-safe if nothing matches.
CLASSIFICATION_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule("payment_request", "comms:payment_request", _is_payment),
    ClassificationRule("credential_request", "comms:credential_request", _is_credential),
    ClassificationRule("instruction_to_act", "comms:instruction_to_act", _is_instruction),
    ClassificationRule("informational_statement", "comms:informational_statement", _is_communication),
)


# --- 2. Derivation rules -------------------------------------------------------

@dataclass(frozen=True)
class DerivationRule:
    """A forward-chaining rule. `derive` returns a list of (fact, reason) pairs given
    a classified assertion; each becomes an `inferred` entry carrying its chain."""

    name: str
    derive: Callable[[ClassifiedAssertion], list]
    version: str = "1"


def _derive_high_risk(c: ClassifiedAssertion) -> list:
    """A high-risk requested-action subtype derives a `needs_review` fact. This is a
    routing derivation, not a trust promotion: it never confers trust or actionable
    status (that would violate a constraint). It exists so the reasoner-soundness
    test has a derived fact to check the chain of."""
    high_risk = {"comms:payment_request", "comms:credential_request", "comms:instruction_to_act"}
    if c.type_name in high_risk:
        return [("needs_human_review", [c.assertion_id, c.type_name])]
    return []


DERIVATION_RULES: tuple[DerivationRule, ...] = (
    DerivationRule("high_risk_needs_review", _derive_high_risk),
)


# --- 3. Constraint axioms ------------------------------------------------------

@dataclass(frozen=True)
class Violation:
    constraint: str
    assertion_id: str
    detail: str


def check_constraints(classified: list[ClassifiedAssertion]) -> list[Violation]:
    """Evaluate the constraint axioms (predicates named in the ontology's constraint
    vocabulary) over the classified batch. A violation is a Gjallarhorn event. These
    encode the load-bearing invariants as checkable axioms."""
    violations: list[Violation] = []
    for c in classified:
        # no_tainted_actionable: a TAINTED assertion must never be actionable.
        if c.trust_level == "trust:TAINTED" and c.actionable:
            violations.append(
                Violation("no_tainted_actionable", c.assertion_id,
                          "a tainted assertion is marked actionable")
            )
        # action_critical_must_gate: enforced after flow-to-sink runs, checked in the
        # engine where the reachable set is known; see engine.check_gating.
    return violations


# --- 4. Flow-to-sink propagation ----------------------------------------------
#
# Reproduces the substrate spike's proven algorithm (D43, conservative mode D44,
# `spike/substrate/reachability.py`). A value is action-critical iff a directed path
# reaches a sink in the agent's reachable sink set (agent-scoped, D24; cross-domain,
# D30). Here it is computed over one batch's flow graph. The live system maintains it
# incrementally in the store; the spike proved that is sound and cheap. For a
# per-batch classification pass a direct backward reachability from the sink set is
# the correct and simplest form, and it is exact.

def action_critical_set(
    flow_edges: list[tuple[str, str]],
    sinks: frozenset[str],
) -> set[str]:
    """Return the set of node ids that can reach any sink, by any path. Backward BFS
    from the sink set over reversed edges. This is the agent-scoped, cross-domain
    reachability of obligation 8.4: `flow_edges` is the global flow graph across
    domains, `sinks` is THIS agent's consequential sink set."""
    # Build reverse adjacency.
    preds: dict[str, list[str]] = {}
    for src, dst in flow_edges:
        preds.setdefault(dst, []).append(src)
    critical: set[str] = set(sinks)
    queue = deque(sinks)
    while queue:
        node = queue.popleft()
        for pred in preds.get(node, ()):
            if pred not in critical:
                critical.add(pred)
                queue.append(pred)
    # A sink is action-critical by definition; but only sinks that actually exist in
    # the graph or the agent's set are meaningful. Keep the full set including sinks.
    return critical
