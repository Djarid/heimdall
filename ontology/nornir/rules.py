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
#
# Cross-domain classification priority principle (decision D31, resolving D51):
# when more than one rule matches, the winner is chosen by, in order,
#   1. RISK TIER: the highest-risk matching type wins. This guarantees a value is
#      never masked DOWN to a lower-risk or inert type, which is the load-bearing
#      safety property (invariant 3.11). A high-risk value always beats an inert one.
#   2. SPECIFICITY: within the top tier, a rule matching a narrower, stronger signal
#      beats a broad one (higher `specificity` wins).
#   3. TIE -> HUMAN REVIEW: if two rules are in the top tier with equal specificity
#      and name DIFFERENT types, that is a genuine tie. Nornir does not silently pick
#      one; it routes to human review. Never guess on a true tie.
# This replaces the earlier "first registered wins", which made cross-domain order an
# accident of import order (D51). Registration order is no longer load-bearing.


class RiskTier:
    """Risk tiers, higher number is higher risk. A higher tier always wins the
    classification contest, so nothing is masked down to inert.

    FALLBACK is the lowest tier: the fail-closed default (`comms:unrecognised_request`)
    that fires only when NO positive rule of any domain matched. It sits BELOW inert
    so that a positive inert classification from any domain (a calendar entry, a
    financial statement, a genuine informational statement) wins over "nothing
    matched, so review". This is subtle but important: unrecognised_request is not
    competing on content merit, it is the last resort, so it must lose to any positive
    match. It still routes to human review, so an evasive request that matches no
    positive rule lands in review rather than being assumed harmless.

    INERT is a positively-classified low-risk type (an informational statement that
    earned it, a calendar entry, a financial statement). HIGH is a known
    consequential type. There is no REVIEW tier between them: a communication either
    earns a positive type or falls to the FALLBACK last resort."""

    FALLBACK = -100
    INERT = 0
    HIGH = 100


@dataclass(frozen=True)
class ClassificationRule:
    """A classification rule. `test` returns True if the assertion is of `type_name`.
    `risk_tier` and `specificity` drive the cross-domain priority principle (D31):
    higher risk wins, then higher specificity, then a genuine tie routes to review.
    `version` tracks the rule as code."""

    name: str
    type_name: str
    test: Callable[[MarshalledAssertion], bool]
    risk_tier: int = RiskTier.INERT
    specificity: int = 0
    version: str = "1"


def text_of(a: MarshalledAssertion) -> str:
    """The concatenated extracted text a rule matches against, lower-cased. Reading
    it is describing untrusted content, not obeying it. Exposed for domain rule
    modules so every domain matches over the same field set consistently."""
    parts = []
    for key in ("subject_extracted", "requested_action_summary"):
        v = a.fields.get(key)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


# The classification-rule registry. Domain rule modules append their rules here at
# import time through `register_classification_rule`. This is what makes the domain
# attach test (D29) hold for rules as well as for types: a new domain contributes a
# sibling rule module that registers its rules; it never edits another domain's rules
# or a shared central list. Order of registration no longer decides the winner (D31):
# the risk-tier / specificity / tie-to-review principle does.
_CLASSIFICATION_REGISTRY: list[ClassificationRule] = []


def register_classification_rule(rule: ClassificationRule, priority: int | None = None) -> None:
    """Register a domain classification rule. `priority` is accepted for backward
    compatibility but is no longer load-bearing (D31): risk_tier and specificity on
    the rule decide the winner. Idempotent per rule name: re-registering the same name
    replaces the earlier entry, so a reload in a test does not duplicate rules."""
    _CLASSIFICATION_REGISTRY[:] = [
        r for r in _CLASSIFICATION_REGISTRY if r.name != rule.name
    ]
    _CLASSIFICATION_REGISTRY.append(rule)


def classification_rules() -> tuple[ClassificationRule, ...]:
    """All registered rules. Order is not significant; the classify function applies
    the D31 priority principle over the full matching set."""
    return tuple(_CLASSIFICATION_REGISTRY)


# The outcome of classification: a chosen type, or a tie that must go to review.
@dataclass(frozen=True)
class ClassificationOutcome:
    type_name: str | None      # the winning type, or None if a genuine tie
    matched_rule: str          # the winning rule name, or "" for tie / no match
    tie: bool = False          # True if two top-tier rules disagreed
    tie_candidates: tuple = ()  # the tied type names, for the audit trail


def classify_assertion(a: MarshalledAssertion) -> ClassificationOutcome:
    """Apply the D31 cross-domain priority principle to one assertion.

    Collect every matching rule, then choose by (risk tier desc, specificity desc).
    If the single top candidate is unambiguous, it wins. If two or more top
    candidates (equal top risk tier and equal top specificity) name different types,
    it is a genuine tie and the outcome routes to human review rather than guessing.
    No match at all returns type_name=None with tie=False (the caller applies the
    UNCLASSIFIED fail-safe)."""
    matches = [r for r in _CLASSIFICATION_REGISTRY if r.test(a)]
    if not matches:
        return ClassificationOutcome(type_name=None, matched_rule="")

    top_tier = max(r.risk_tier for r in matches)
    tier_matches = [r for r in matches if r.risk_tier == top_tier]
    top_spec = max(r.specificity for r in tier_matches)
    winners = [r for r in tier_matches if r.specificity == top_spec]

    distinct_types = {r.type_name for r in winners}
    if len(distinct_types) == 1:
        w = winners[0]
        return ClassificationOutcome(type_name=w.type_name, matched_rule=w.name)

    # Genuine tie at the top: equal risk tier, equal specificity, different types.
    # Route to human review; never silently pick. The value keeps the top risk tier,
    # so it is still gated, and a human resolves which type it is.
    return ClassificationOutcome(
        type_name=None,
        matched_rule="",
        tie=True,
        tie_candidates=tuple(sorted(distinct_types)),
    )


# --- 2. Derivation rules -------------------------------------------------------

@dataclass(frozen=True)
class DerivationRule:
    """A forward-chaining rule. `derive` returns a list of (fact, reason) pairs given
    a classified assertion; each becomes an `inferred` entry carrying its chain."""

    name: str
    derive: Callable[[ClassifiedAssertion], list]
    version: str = "1"


# High-risk type registry. Each domain declares which of its types are high-risk by
# calling `register_high_risk_types`; the shared derivation rule reads this set. This
# keeps the derivation rule authored once over the shared structure
# (`ONTOLOGY_CONSTRUCTION.md` section 6, flow-to-sink is authored once, not per
# domain), while letting each domain contribute its own high-risk types without
# editing the rule. A domain attaches by adding to this set, not by editing here.
_HIGH_RISK_TYPES: set[str] = set()


def register_high_risk_types(*type_names: str) -> None:
    _HIGH_RISK_TYPES.update(type_names)


def high_risk_types() -> frozenset[str]:
    return frozenset(_HIGH_RISK_TYPES)


def _derive_high_risk(c: ClassifiedAssertion) -> list:
    """A high-risk type derives a `needs_human_review` fact. This is a routing
    derivation, not a trust promotion: it never confers trust or actionable status
    (that would violate a constraint). Authored once over the shared structure; the
    set of high-risk types is contributed per domain (see `_HIGH_RISK_TYPES`)."""
    if c.type_name in _HIGH_RISK_TYPES:
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
