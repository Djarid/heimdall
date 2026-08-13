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


@dataclass(frozen=True)
class MarshalledAssertion:
    """One assertion marshalled from untrusted content.

    `assertion_id` is a stable id within a batch. `taint_class` is the medium's taint
    (set at Bifrost, e.g. taint:EXTERNAL_COMMS); it is always an external/tainted
    class in Phase 1. `fields` carries the extracted values (the PoC schema). `flows`
    lists the ids of other assertions or sink names this assertion's value can flow
    into, which is the flow-to-sink edge set (Fenrir/Gjoll would derive these from
    the real data flow; a test supplies them explicitly).
    """

    assertion_id: str
    taint_class: str
    fields: dict = field(default_factory=dict)
    flows: tuple = ()  # ids/sink-names this value can flow into


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
