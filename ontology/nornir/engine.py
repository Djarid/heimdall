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
    CLASSIFICATION_RULES,
    DERIVATION_RULES,
    Violation,
    action_critical_set,
    check_constraints,
)
from ..yggdrasil.unclassified import UNCLASSIFIED


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

    def _classify_one(self, a: MarshalledAssertion) -> ClassifiedAssertion:
        for rule in CLASSIFICATION_RULES:
            if rule.test(a):
                node = self.onto.nodes.get(rule.type_name)
                return ClassifiedAssertion(
                    assertion_id=a.assertion_id,
                    type_name=rule.type_name,
                    # A tainted assertion is never actionable (constraint), and Phase
                    # 1 marks nothing actionable regardless.
                    actionable=False,
                    trust_level="trust:TAINTED",
                    taint_class=a.taint_class,
                    fields=dict(a.fields),
                    matched_rule=rule.name,
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
        classified = [self._classify_one(a) for a in assertions]

        # 2. Derivations.
        for c in classified:
            for rule in DERIVATION_RULES:
                for fact, chain in rule.derive(c):
                    c.inferred.append({"fact": fact, "chain": chain, "rule": rule.name})

        # 3. Flow-to-sink, agent-scoped. Build the global flow graph from the batch:
        # every assertion's `flows` are edges from the assertion id to the target
        # (another assertion id or a sink name). Reachability is against THIS agent's
        # consequential sink set (D24, D30). Phase 1's default set is empty, so
        # nothing is action-critical unless the agent context supplies sinks.
        flow_edges: list[tuple[str, str]] = []
        for a in assertions:
            for target in a.flows:
                flow_edges.append((a.assertion_id, target))
        critical = action_critical_set(flow_edges, ctx.consequential_sinks)
        for c in classified:
            c.action_critical = c.assertion_id in critical

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
