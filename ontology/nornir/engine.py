"""The Nornir runner: classify, derive, propagate action-critical, check constraints.

Deterministic, no model (invariant 3.1). Given a loaded ontology, an agent context
(the control surface, D20/D24) and a batch of marshalled assertions, it produces
classified assertions and any constraint violations. The order matters and is fixed:

1. Classify each assertion (first matching rule wins; no match is the fail-safe).
2. Forward-chain derivations, each derived fact carrying its assertion chain.
3. Propagate action-critical status by flow-to-sink reachability over the batch's
   flow graph against the agent's sink set (agent-scoped, cross-domain).
4. Check constraint axioms, including the gating axiom that any value reaching a
   consequential sink must be marked action-critical (the critical class of 8.2).

Nothing acts on the extracted field content. Classification reads it to type it;
that is describing untrusted content, not obeying it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..yggdrasil.core import Ontology
from ..yggdrasil.control_surface import AgentContext, resolve
from .assertions import ClassifiedAssertion, MarshalledAssertion
from .rules import (
    DERIVATION_RULES,
    Violation,
    action_critical_set,
    check_constraints,
    classify_assertion,
)
from . import domain_rules
from ..yggdrasil.unclassified import UNCLASSIFIED, HIGH_RISK_UNRESOLVED


@dataclass
class NornirResult:
    classified: list[ClassifiedAssertion]
    violations: list[Violation] = field(default_factory=list)
    action_critical: set = field(default_factory=set)

    def by_id(self, assertion_id: str) -> ClassifiedAssertion:
        for c in self.classified:
            if c.assertion_id == assertion_id:
                return c
        raise KeyError(assertion_id)

    def coverage(self) -> float:
        """Fraction classified to a known type versus the fail-safe (obligation 8.1).
        A reported number, not a pass/fail."""
        if not self.classified:
            return 0.0
        covered = sum(1 for c in self.classified if c.type_name != UNCLASSIFIED)
        return covered / len(self.classified)


class Nornir:
    def __init__(self, ontology: Ontology) -> None:
        self.onto = ontology
        # Load every domain's classification and derivation rules into the shared
        # registries. Each domain registers its own; adding a domain is a new sibling
        # module here, never an edit to another domain's rules (the D29 attach test
        # for rules). Idempotent, so constructing Nornir twice does not duplicate.
        domain_rules.register_all()

    def _classify_one(self, a: MarshalledAssertion) -> ClassifiedAssertion:
        # Apply the D31 cross-domain priority principle: highest risk tier wins, then
        # specificity, and a genuine tie routes to review rather than guessing.
        outcome = classify_assertion(a)
        if outcome.tie:
            # A genuine tie between high-risk types. Route to review as a distinct,
            # high-risk-gated outcome; never silently pick one. Not a downgrade: the
            # HIGH_RISK_UNRESOLVED type is high-risk, so the value is still gated.
            return ClassifiedAssertion(
                assertion_id=a.assertion_id,
                type_name=HIGH_RISK_UNRESOLVED,
                actionable=False,
                trust_level="trust:TAINTED",
                taint_class=a.taint_class,
                fields=dict(a.fields),
                route="human_review",
                matched_rule="",
                tie_candidates=outcome.tie_candidates,
            )
        if outcome.type_name is not None:
            # Honour a type's declared route: a type may carry route="human_review"
            # in the ontology (e.g. comms:unrecognised_request, the fail-closed
            # default). Read it from the node rather than hardcoding, so a domain that
            # adds a review-routed type does not need an engine change.
            node = self.onto.nodes.get(outcome.type_name)
            route = "normal"
            if node is not None and node.attrs.get("route") == "human_review":
                route = "human_review"
            return ClassifiedAssertion(
                assertion_id=a.assertion_id,
                type_name=outcome.type_name,
                # A tainted assertion is never actionable (constraint), and Phase 1
                # marks nothing actionable regardless.
                actionable=False,
                trust_level="trust:TAINTED",
                taint_class=a.taint_class,
                fields=dict(a.fields),
                route=route,
                matched_rule=outcome.matched_rule,
            )
        # No rule matched: the fail-safe. Never a guess, never trusted or actionable.
        return ClassifiedAssertion(
            assertion_id=a.assertion_id,
            type_name=UNCLASSIFIED,
            actionable=False,
            trust_level="trust:TAINTED",
            taint_class=a.taint_class,
            fields=dict(a.fields),
            route="human_review",
            matched_rule="",
        )

    def run(
        self,
        assertions: list[MarshalledAssertion],
        agent: AgentContext | None = None,
    ) -> NornirResult:
        ctx = resolve(agent)
        # 1. Classify.
        classified = [self._classify_one(a) for a in assertions]

        # 2. Flow-to-sink, agent-scoped. Build the global flow graph from the batch:
        # every assertion's `flows` are edges from the assertion id to the target
        # (another assertion id or a sink name). Reachability is against THIS agent's
        # consequential sink set (D24, D30). Phase 1's default set is empty, so
        # nothing is action-critical unless the agent context supplies sinks. This runs
        # BEFORE derivations so a derivation can chain on the action_critical label
        # (forward-chaining should see all base facts).
        flow_edges: list[tuple[str, str]] = []
        for a in assertions:
            for target in a.flows:
                flow_edges.append((a.assertion_id, target))
        critical = action_critical_set(flow_edges, ctx.consequential_sinks)
        for c in classified:
            c.action_critical = c.assertion_id in critical

        # 3. Derivations (forward-chaining), now able to key on both the classified
        # type and the flow-to-sink label. Each derived fact records the rule that
        # produced it, so the soundness test can check it against that rule's own
        # entailment oracle (obligation 8.3).
        for c in classified:
            for rule in DERIVATION_RULES:
                for fact, chain in rule.derive(c):
                    c.inferred.append({"fact": fact, "chain": chain, "rule": rule.name})

        # 4. Constraints, including the gating axiom.
        violations = check_constraints(classified)
        violations.extend(self._check_gating(assertions, classified, critical, ctx))

        return NornirResult(classified=classified, violations=violations, action_critical=critical)

    def _check_gating(
        self,
        assertions: list[MarshalledAssertion],
        classified: list[ClassifiedAssertion],
        critical: set,
        ctx: AgentContext,
    ) -> list[Violation]:
        """action_critical_must_gate: any assertion whose value can reach a
        consequential sink must be marked action-critical. Because we compute the
        reachable set and set the flag from it, this holds by construction here; the
        check exists to catch a future regression where the flag and the reachable
        set diverge. A divergence would be the critical misclassification of 8.2."""
        violations: list[Violation] = []
        for c in classified:
            reaches = c.assertion_id in critical
            if reaches and not c.action_critical:
                violations.append(
                    Violation(
                        "action_critical_must_gate",
                        c.assertion_id,
                        "value can reach a consequential sink but is not marked action-critical",
                    )
                )
        return violations
