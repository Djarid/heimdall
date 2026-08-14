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


# The inert-earning guard, shared across all domains (D69). A repository-access review
# found that only the communications inert rule required "no imperative present"; the
# scheduling, finance and publication inert rules were bare keyword matches, so
# consequential content that positively earned one of their signals (a payment framed
# as a "reminder" or an "article") was typed inert and skipped both the gate and
# review, a measured false-inert break (D67). This guard is authored once over the
# shared structure (like the flow-to-sink rule, ONTOLOGY_CONSTRUCTION.md section 6) so
# every domain's inert rule applies the SAME discipline consistently: a value may only
# be typed inert if it carries NO imperative and NO consequence signal. It is not a
# blacklist of attacks (invariant 3.5, D54/D55): it is a conservative "does this ask
# for, or describe, something with an effect?" test that, when in doubt, denies the
# inert label and lets the value fall through to the fail-closed default (review). An
# imperfect detector here only ever means "more review", never "silent inert".
_IMPERATIVE_OR_CONSEQUENCE = re.compile(
    # request/imperative shapes (does it ask the reader to do something?)
    r"\b((please|kindly) (?!find|see|note|be advised|disregard|ignore)\w+|"
    r"can you|could you|would you|need you to|make sure|ensure you|"
    r"send|buy|purchase|confirm|provide|share|reply with|respond with|"
    r"go to|visit|use the (new )?(details|coordinates|ones)|as (we )?discussed|as agreed|"
    r"(?<!no )action (needed|required)|get back to me|"
    # a general "add/give/grant/put X to/into Y" request shape (a grammatical pattern,
    # not a specific attack phrase): captures access grants like "add the new starter
    # to the room" without enumerating the wording.
    r"(add|give|grant|put|move|send)\s+\w+(\s+\w+){0,4}\s+(to|into|onto)\b|"
    # consequence shapes (does it concern something with an effect, even without an
    # explicit imperative?): money, access, execution, exfiltration, security state
    r"move (the |money|funds)|transfer|remit|pay|wire|disburse|settle|invoice|"
    r"grant|access|permission|run|execute|deploy|delete|disable|"
    r"forward (the|all)|exfiltrate|the recipe|take care of|"
    r"the usual (monthly )?(thing|arrangement))\b"
)


def carries_imperative_or_consequence(a: MarshalledAssertion) -> bool:
    """True if the assertion's text carries an imperative OR a consequence signal, so
    it must not earn an inert type (D69). Shared by every domain's inert rule."""
    return bool(_IMPERATIVE_OR_CONSEQUENCE.search(text_of(a)))


# The referential-completeness guard, shared across all domains (D72). This is a REDUCTION
# of the false-inert break, not a closure, and it is honest to say so up front: the D69
# guard keyed on imperative and consequence VERBS, so an attacker who passivises the verb
# ("the standing order to the contractor is set to go out", the fi-19 break) earns inert.
# This guard keys on a different structural shape: a message that DEFERS its consequence to
# a referent OUTSIDE itself. A deictic/definite pointer ("the thing we discussed", "the
# usual arrangement", "as agreed", "the standing order") combined with a motion/completion
# phrasing ("is set to go", "now in motion", "proceeds", "going ahead") is the shape of
# "a consequence is happening, and I am pointing at it rather than stating it". A genuinely
# informational statement reports something COMPLETE within the message ("the newsletter is
# set to go out tomorrow" names its own subject), so it does not match. Measured on the
# 38-case corpus this re-routes zero real inert cases (no friction) and closes fi-19 and the
# pure-euphemism probe the D69/subject-matter approaches missed. It does NOT close the hole:
# a pure metaphor ("the wheels are turning on the matter") expresses the same deixis+motion
# without the keywords and still earns inert, and that case is kept in the corpus as the
# named residual (fi-20). So this is the SAME category as D69, a reduction that keys on
# shape rather than topic, and is fail-open on the phrasing it does not match. It is NOT a
# blacklist of attack topics (invariant 3.5): it never enumerates payments/access/exfil, it
# tests a grammatical deferral shape, and when in doubt it denies inert and falls through to
# review. The load-bearing point (D67-fix stays OPEN) is that no content pattern can separate
# a passively-phrased consequence from a genuine informational statement without world
# knowledge, which invariant 3.1 keeps off the classification path.
_DEFERRED_DEIXIS = re.compile(
    r"\b(the (thing|matter|arrangement|usual|standing order|order|payment|transfer|deal)\b|"
    r"as (we )?(discussed|agreed|arranged)|the one (from|we)|"
    r"it (will|is set)|that (we )?spoke)\b"
)
_DEFERRED_MOTION = re.compile(
    r"\b(set to (go|proceed|run|happen|execute|send)|going out|goes out|"
    r"now in motion|in motion|proceeds?|going ahead|"
    r"will (go|proceed|happen|run)|is (being )?actioned)\b"
)


def defers_consequence_to_context(a: MarshalledAssertion) -> bool:
    """True if the assertion defers a consequence to a referent outside the message (a
    deictic/definite pointer plus a motion/completion phrasing), so it must not earn an
    inert type (D72). A REDUCTION, not a closure: keys on a deferral SHAPE, not attack
    topics, and is fail-open on phrasings it does not match (see fi-20, the residual)."""
    text = text_of(a)
    return bool(_DEFERRED_DEIXIS.search(text) and _DEFERRED_MOTION.search(text))


def earns_inert(a: MarshalledAssertion) -> bool:
    """The shared inert-earning discipline every domain's inert rule applies over its own
    positive signal: a value may earn an inert type only if it carries no imperative or
    consequence signal (D69) AND does not defer a consequence to out-of-message context
    (D72). When in doubt this denies inert and falls through to the fail-closed default
    (review), never to a silent inert type (invariant 3.5)."""
    return not carries_imperative_or_consequence(a) and not defers_consequence_to_context(a)


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

    # A genuine tie at the top tier: equal risk tier, equal specificity, different
    # types. What happens next depends on whether the tie is GATED (D52, refined by
    # D60):
    #   - If the top tier is HIGH (or any gated tier), route to human review. A human
    #     must resolve which consequential type applies; the value keeps the high-risk
    #     tier so it is still gated meanwhile. Never silently pick a gated type.
    #   - If the top tier is INERT or below, no gating decision hinges on the choice
    #     (neither candidate is consequential), so routing to review would be pure
    #     friction. Resolve deterministically by name and classify. Still safe: an
    #     inert type is inert whichever of the tied labels it takes.
    if top_tier >= RiskTier.HIGH:
        return ClassificationOutcome(
            type_name=None,
            matched_rule="",
            tie=True,
            tie_candidates=tuple(sorted(distinct_types)),
        )
    winners_by_name = sorted(winners, key=lambda r: r.type_name)
    chosen = winners_by_name[0]
    return ClassificationOutcome(type_name=chosen.type_name, matched_rule=chosen.name)


# --- 2. Derivation rules -------------------------------------------------------

@dataclass(frozen=True)
class DerivationRule:
    """A forward-chaining rule. `derive` returns a list of (fact, chain) pairs given a
    classified assertion (with its flow-to-sink `action_critical` label already set,
    because derivations run after flow-to-sink). Each pair becomes an `inferred` entry
    carrying its chain.

    `entails(assertion, fact) -> bool` is the rule's own soundness oracle: it states
    the condition under which `fact` is legitimately derivable from the assertion. The
    reasoner-soundness test (obligation 8.3) checks every derived fact against the
    entailment of the rule that produced it, so soundness is verified per rule rather
    than by the harness hardcoding knowledge of one fact. A rule whose `derive`
    produces a fact its own `entails` rejects is caught as unsound. This is what lets
    a deliberately-unsound rule be caught by the suite (the 8.3 negative control),
    proving the test bites, in the same spirit as D10 and D55."""

    name: str
    derive: Callable[[ClassifiedAssertion], list]
    entails: Callable[[ClassifiedAssertion, str], bool]
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


def _is_high_risk_type(type_name: str) -> bool:
    """A type is high-risk if a domain declared it so, OR it is the high-risk tie
    outcome. HIGH_RISK_UNRESOLVED is not in the per-domain registry (it is a fail-safe
    node), but a value routed there is high-risk and gated, so derivations that key on
    high-risk must include it."""
    return type_name in _HIGH_RISK_TYPES or type_name == "unclassified:high_risk_unresolved"


def _derive_high_risk(c: ClassifiedAssertion) -> list:
    """A high-risk type derives a `needs_human_review` fact. A routing derivation, not
    a trust promotion: it never confers trust or actionable status. Authored once over
    the shared structure; the set of high-risk types is contributed per domain."""
    if _is_high_risk_type(c.type_name):
        return [("needs_human_review", [c.assertion_id, c.type_name])]
    return []


def _entails_high_risk(c: ClassifiedAssertion, fact: str) -> bool:
    return fact == "needs_human_review" and _is_high_risk_type(c.type_name)


def _derive_second_approval(c: ClassifiedAssertion) -> list:
    """Chained inference (real forward-chaining over two base facts): a value that is
    BOTH high-risk by type AND action-critical by flow-to-sink reachability derives
    `needs_second_approval`. The chain records both premises. This is the staging
    signal that matters: a high-risk value that can actually reach a consequential
    sink warrants a second approver, not just review. It depends on the flow-to-sink
    label, which is why derivations run after flow-to-sink. It confers no trust and no
    actionable status; it raises scrutiny, which always fails safe."""
    if _is_high_risk_type(c.type_name) and c.action_critical:
        return [("needs_second_approval", [c.assertion_id, c.type_name, "action_critical"])]
    return []


def _entails_second_approval(c: ClassifiedAssertion, fact: str) -> bool:
    return (
        fact == "needs_second_approval"
        and _is_high_risk_type(c.type_name)
        and c.action_critical
    )


DERIVATION_RULES: tuple[DerivationRule, ...] = (
    DerivationRule("high_risk_needs_review", _derive_high_risk, _entails_high_risk),
    DerivationRule("action_critical_needs_second_approval",
                   _derive_second_approval, _entails_second_approval),
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
