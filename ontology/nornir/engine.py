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
    check_constraints,
    classify_assertion,
)
from . import domain_rules
from ..yggdrasil.unclassified import UNCLASSIFIED, HIGH_RISK_UNRESOLVED
# The false-inert mitigations, wired into the live pipeline (D84). None of them
# depends on the classifier being right: each only ever ADDS caution, so composing
# them with the existing fail-closed discipline can never introduce a silent
# downgrade. They read STRUCTURAL inputs (slot bindings, flow edges) off the
# marshalled assertion, not the classifier's content pattern (D79, D80, D82).
from .state_delta import StateOracle, SlotRef, dict_oracle, evaluate as evaluate_deltas
from .consequence_axis import (
    classify_two_dimensional,
    flow_to_sink_signal,
    state_delta_signal,
)
from .promotion_policy import (
    PromotionDecision,
    ReviewPriority,
    SourcedValue,
    evaluate_promotion,
    review_priority,
)


@dataclass
class NornirResult:
    classified: list[ClassifiedAssertion]
    violations: list[Violation] = field(default_factory=list)
    action_critical: set = field(default_factory=set)
    # Promotion decisions per consequential slot (D84, wiring D82). A value that would
    # set a consequential slot is not promotable to a trusted fact on a single source's
    # word: it needs independent corroboration or human approval. Keyed by SlotRef.key().
    # Empty when no assertion proposed a consequential-slot fact. This never grants
    # trust; it only ever WITHHOLDS promotion, so it composes with the fail-closed
    # discipline and cannot introduce a silent downgrade.
    promotions: dict = field(default_factory=dict)

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

    def coverage_gaps(self) -> dict:
        """The coverage-gap capture process (ONTOLOGY_CONSTRUCTION.md section 7, D59).

        Everything that landed in the review queue rather than a positive type is a
        signal about where coverage is thin. This groups those assertions by the
        REASON they need review, so a human (or, later, Odin under the D27 provenance
        gate) can see what to extend, demand-driven, rather than discovering gaps by
        luck. It reports, it does not act: growing coverage stays hand-authored and
        human-curated (D26).

        Three buckets, none of them a safety failure (all fail closed):
          - unclassified: matched no rule at all (UNCLASSIFIED_DATA_ASSERTION). The
            content is not recognisably anything the ontology covers.
          - unrecognised_request: a communication carrying an imperative we could not
            positively classify (the fail-closed default, D54).
          - high_risk_tie: a genuine cross-domain tie routed to review (D52).
        Each bucket carries the assertion ids and a small sample of the extracted
        subject/summary, so the review is actionable.
        """
        buckets: dict[str, list] = {"unclassified": [], "unrecognised_request": [], "high_risk_tie": []}
        for c in self.classified:
            key = None
            if c.type_name == UNCLASSIFIED:
                key = "unclassified"
            elif c.type_name == "comms:unrecognised_request":
                key = "unrecognised_request"
            elif c.type_name == HIGH_RISK_UNRESOLVED:
                key = "high_risk_tie"
            if key is None:
                continue
            sample = c.fields.get("subject_extracted") or c.fields.get("requested_action_summary") or ""
            buckets[key].append({"id": c.assertion_id, "sample": sample[:80],
                                 "tie": list(getattr(c, "tie_candidates", ()) or ())})
        return {
            "review_total": sum(len(v) for v in buckets.values()),
            "reviewed_fraction": (sum(len(v) for v in buckets.values()) / len(self.classified))
                                 if self.classified else 0.0,
            "by_reason": buckets,
        }


class Nornir:
    def __init__(self, ontology: Ontology, flow_backend=None,
                 state_oracle: "StateOracle | None" = None) -> None:
        self.onto = ontology
        # The state oracle answers "what value is currently stored for this slot?" for
        # the state-delta detector (D79). It defaults to an empty in-memory store, in
        # which any proposed consequential-slot value is a first-value delta (a new
        # consequential fact IS a delta, D79). A live deployment injects a Mímisbrunnr-
        # backed oracle so a delta is a genuine change against stored state. Kept
        # injectable and defaulted so the core path carries no store dependency.
        self.state_oracle: StateOracle = state_oracle or dict_oracle({})
        # The inert (low-risk) type set, read from the ontology exactly as the harness
        # derives it (risk=low plus the fail-safe). The consequence axis needs it to
        # know whether the speech-act type is inert; deriving it here keeps the engine
        # self-contained and correct as domains add low-risk types.
        self._inert_types = frozenset(
            {n.name for n in ontology.nodes.values() if n.attrs.get("risk") == "low"}
            | {UNCLASSIFIED}
        )
        # The flow-to-sink backend computes the agent-scoped action-critical set from
        # the batch's flow edges and the agent's sinks. It defaults to the proven
        # in-memory backward reachability (dependency-free, D01). A caller may inject
        # a MemgraphFlowBackend to run the same determination over a live store (D57,
        # D63); nothing about the store leaks into the default path.
        from .flow_backends import in_memory
        self.flow_backend = flow_backend or in_memory
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
        # Compute the action-critical set via the configured backend. In-memory by
        # default; a Memgraph-backed backend runs the same determination over the live
        # store (D63). Both return the same set for the same input.
        critical = self.flow_backend(flow_edges, ctx.consequential_sinks)
        for c in classified:
            c.action_critical = c.assertion_id in critical
            # D100: stamp the RESOLVED classify-time set that produced the label just
            # above, from the same expression already passed to self.flow_backend, so
            # the stamp and the reachability determination cannot diverge without two
            # separate edits. Taken from `ctx` (resolved), never from the raw `agent`.
            c.consequential_sinks_at_classify = ctx.consequential_sinks

        # 2b. False-inert mitigations in depth (D84, wiring D79/D80/D82). For each
        # assertion, judge consequence on the SECOND axis the inert speech-act type
        # cannot suppress (D80), fed by two structural signals an attacker does not
        # author: a state delta on a declared consequential slot (D79) and a flow edge
        # reaching a consequential sink (the action-critical label just computed). The
        # effective-inert conjunction is what downstream reads; the classifier's own
        # type is left untouched, so layer one's measured rate is unchanged and the RED
        # bar stays honest. This only ever ADDS caution.
        by_marshalled = {a.assertion_id: a for a in assertions}
        for c in classified:
            a = by_marshalled.get(c.assertion_id)
            signals = []
            if a is not None and a.proposed_facts:
                verdict = evaluate_deltas(list(a.proposed_facts), self.state_oracle)
                if verdict.deny_inert:
                    signals.extend(state_delta_signal(r) for r in verdict.reasons())
            if c.action_critical:
                signals.append(
                    flow_to_sink_signal("value reaches a consequential sink for this agent")
                )
            speech_act_inert = c.type_name in self._inert_types
            two_d = classify_two_dimensional(c.type_name, speech_act_inert, signals)
            c.consequence = two_d.consequence
            c.effective_inert = two_d.effective_inert
            c.consequence_reasons = tuple(two_d.consequence.reasons())
            # Graded review priority (D82): an inert-in-effect value that still touches
            # a consequential slot earns LOW-priority review rather than none.
            touches = bool(a is not None and a.proposed_facts)
            c.review_priority = review_priority(
                two_d.effective_inert, touches, two_d.consequence.has_structural
            ).value

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

        # 5. Promotion policy (D84, wiring D82). Gather every proposed fact on a slot
        # across the batch, grouped by slot, each carrying its source, and decide
        # whether that slot may be promoted to a trusted fact. A consequential slot
        # needs corroboration from independent sources or human approval; a single
        # source is not enough. Disagreeing sources never promote and escalate. This
        # runs over the same structural bindings the state-delta detector reads.
        promotions = self._evaluate_promotions(assertions)

        return NornirResult(
            classified=classified,
            violations=violations,
            action_critical=critical,
            promotions=promotions,
        )

    def _evaluate_promotions(self, assertions: list[MarshalledAssertion]) -> dict:
        """Group proposed facts by slot and evaluate promotion for each (D82). Returns a
        mapping of SlotRef.key() to PromotionDecision. Only slots that some assertion
        proposes a value for appear; a batch with no structural bindings yields {}."""
        by_slot: dict[str, list[SourcedValue]] = {}
        for a in assertions:
            for pf in a.proposed_facts:
                key = pf.slot.key()
                by_slot.setdefault(key, []).append(
                    SourcedValue(slot=pf.slot, value=pf.value,
                                 source=a.source or a.assertion_id)
                )
        return {key: evaluate_promotion(cands) for key, cands in by_slot.items()}

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
