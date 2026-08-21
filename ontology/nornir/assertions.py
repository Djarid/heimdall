"""The marshalled-assertion model: Nornir's input and output.

A `MarshalledAssertion` is what Fenrir produces and Nornir consumes (the marshalling
contract, D28). It is the live analogue of the PoC's extraction envelope: the model
filled the values, the structure is not the model's to emit, and everything is
TAINTED by origin (`ONTOLOGY_CONSTRUCTION.md` section 5). The PoC's four fields
(`sender_extracted`, `subject_extracted`, `requested_action_summary`, `entities`)
arrive here as `fields`, plus the taint class the medium set at Bifrost.

A `ClassifiedAssertion` is Nornir's output: the assertion plus the ontology type it
classified to, whether it is actionable, its trust level, and, once flow-to-sink has
run, whether it is action-critical for the agent in question. Every value is
provenance-stamped and immutable once set; classification adds a type, it never
changes the provenance.

Crucially, `fields` are inert data. Nornir classifies BY them but never ACTS on
them. A classification rule may read `requested_action_summary` to decide the type
is `comms:payment_request`; that is describing the content, not obeying it. The
distinction the PoC established (describe vs obey) holds here: typing a payment
request as such is not making a payment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .state_delta import ProposedFact


@dataclass(frozen=True)
class MarshalledAssertion:
    """One assertion marshalled from untrusted content.

    `assertion_id` is a stable id within a batch. `taint_class` is the medium's taint
    (set at Bifrost, e.g. taint:EXTERNAL_COMMS); it is always an external/tainted
    class in Phase 1. `fields` carries the extracted values (the PoC schema). `flows`
    lists the ids of other assertions or sink names this assertion's value can flow
    into, which is the flow-to-sink edge set (Fenrir/Gjoll would derive these from
    the real data flow; a test supplies them explicitly).

    `proposed_facts` is the STRUCTURAL extraction output (D79): the values the reading
    layer bound to typed slots (`salary_destination = X`). It is what the state-delta
    detector consumes to judge consequence by effect rather than by wording. An
    assertion with no structural binding leaves this empty, and the mitigations that
    key on it simply add no caution for that assertion (they only ever ADD caution, per
    D79/D80), so an interpretive-only extraction is not silently downgraded. `source` is
    the provenance identifier (a mailbox, a feed, a document id) the promotion policy
    (D82) uses to count corroboration; it is provenance, never a trust level.
    """

    assertion_id: str
    taint_class: str
    fields: dict = field(default_factory=dict)
    flows: tuple = ()  # ids/sink-names this value can flow into
    proposed_facts: tuple[ProposedFact, ...] = ()  # structural slot bindings (D79)
    source: str = ""  # provenance identifier for corroboration (D82)


@dataclass
class ClassifiedAssertion:
    """Nornir's output for one assertion. Mutable only within a single Nornir run as
    derivation and flow-to-sink fill in fields; treated as immutable thereafter."""

    assertion_id: str
    type_name: str                 # the ontology type it classified to
    actionable: bool               # never True for a tainted assertion (constraint)
    trust_level: str               # trust:TAINTED in Phase 1
    taint_class: str
    fields: dict
    route: str = "normal"          # "human_review" for the fail-safe and for ties
    action_critical: bool = False  # set by flow-to-sink, agent-scoped
    inferred: list = field(default_factory=list)   # derived facts, each with a chain
    matched_rule: str = ""         # which classification rule fired ("" = fail-safe/tie)
    # A genuine cross-domain tie (D31): two top-tier rules of equal specificity named
    # different types. The value is routed to review rather than silently typed. The
    # tied candidates are recorded for the audit trail and so the harness can confirm
    # the tie is a safe (still-gated) outcome, not a downgrade.
    tie_candidates: tuple = ()
    # The two-dimensional consequence outcome (D79/D80), filled by the engine after
    # classification and flow-to-sink. `consequence` is the second axis the inert
    # speech-act type cannot suppress; `effective_inert` is the conjunction downstream
    # reads to decide whether the value may be treated as inert; `review_priority`
    # grades the review queue (D82). All three are set from structural inputs (slot
    # bindings, flow edges), so a mis-classification at layer 1 no longer decides the
    # outcome alone. They are optional so an assertion run without structural extraction
    # simply carries the classifier's own result, unchanged.
    consequence: object | None = None          # ConsequenceAxis (D80)
    effective_inert: bool | None = None        # None until the engine computes it
    consequence_reasons: tuple = ()            # audit strings for the axis
    review_priority: str = ""                  # graded review priority (D82)
    # The RESOLVED classify-time consequential sink set this value was labelled
    # against (D100). Gjoll's no-registry branch derives consequentiality from THIS
    # stamp rather than from the `agent_consequential_sinks` argument supplied at the
    # gate call, so hollowing or swapping that argument no longer disarms the block.
    #
    #   None            = no classify-time provenance for this value. The gate FAILS
    #                     CLOSED and treats the sink as consequential (invariant 3.5).
    #                     Set only by a caller that hand-builds a ClassifiedAssertion.
    #   frozenset()     = classified against an agent with NO consequential sinks. This
    #                     is legitimate and common (the Phase 1 default), and must NEVER
    #                     be read as absent. Test with `is None`, never for truthiness.
    #   frozenset({..}) = the resolved classify-time consequential sink set.
    #
    # This carries NO NEW TRUST ROOT. It is engine output on exactly the same footing
    # as `action_critical` and `trust_level`, which the gate already trusts. A caller
    # able to rewrite `classified_by_id` in process can rewrite this too, and can
    # already rewrite those two; that is an integrity assumption the gate makes today,
    # not one this build introduces.
    consequential_sinks_at_classify: "frozenset[str] | None" = None
