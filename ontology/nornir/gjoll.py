"""Gjoll: the action-time gate that authorises or blocks a consequential action.

This connects two already-proven halves into invariant 3.6's action-critical gate:

- The PoC proved the provenance gate's SHAPE (`poc/sinks.py`): a sink consuming an
  untrusted-derived value as an action instruction is unsafe, checked structurally on
  the wiring, never on the value's content. A safe wiring passes; an unsafe control
  wiring must be caught before it fires (D10).
- This ontology build computes ACTION-CRITICAL status by flow-to-sink transitive
  reachability, agent-scoped and cross-domain (D24, D30, and the substrate binding
  D57). A value is action-critical the moment a path to a consequential sink exists,
  however many reversible hops intervene.

Gjoll is where they meet. It is deterministic, contains no model (invariant 3.1), and
fails closed. The rule, in one line: a consequential action is authorised only if no
parameter it consumes as an action instruction is an action-critical untrusted-derived
value that has not passed the gate.

Why all three conditions matter, and why the gate is not just the PoC gate:

- "untrusted-derived": the value came from tainted content (every marshalled assertion
  is TAINTED by origin, the marshalling contract). This is the PoC's provenance test.
- "action-critical": the value can actually reach a consequential sink by some path.
  A value that is untrusted-derived but cannot reach any consequential sink for this
  agent is inert in effect, and gating it would be friction without safety. This is
  the flow-to-sink dimension the PoC's per-input label could not express, and it is
  what makes the gate sound against MULTI-STEP STATE STAGING: the value is caught at
  the staging write because reachability already marked it action-critical, not only
  at the final consequential step (invariant 3.6, HEIMDALL.md action-critical set
  sizing).
- "consumed as an action": the sink drives an effect from this value, not merely logs
  or stores it. Consuming the same value as inert data is always fine (the PoC's
  describe-vs-obey distinction).

The gate does not choose the wiring; it proves a given wiring safe or unsafe, exactly
as the PoC gate did. A real system must still declare, per sink, how each parameter is
consumed; that declaration is trusted input (the PoC's honest limit, invariant section
4, sink-wiring honesty), and deriving it from real data flow is future work. What Gjoll
adds here is that the action-critical determination is now computed by reachability,
not self-asserted per sink.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .assertions import ClassifiedAssertion


# How a sink consumes a parameter, mirroring the PoC (poc/sinks.py).
CONSUME_INERT = "INERT"    # logged, stored, displayed; never acted upon
CONSUME_ACTION = "ACTION"  # drives an effect (money moved, command run, mail sent)


@dataclass(frozen=True)
class ActionProposal:
    """An agent proposing to fire a consequential action at a sink.

    `sink` is the consequential-sink node id (must be in the agent's
    `consequential_sinks` for the action to be consequential for this agent).
    `consumes` maps each parameter (by assertion id) to how the sink consumes it
    (CONSUME_INERT or CONSUME_ACTION). `declared_safe` records the author's intent for
    reporting only; the gate does not trust it, it re-derives authorisation from the
    consumption mode, the parameter's provenance and its action-critical status."""

    action_id: str
    sink: str
    consumes: dict           # assertion_id -> CONSUME_INERT | CONSUME_ACTION
    declared_safe: bool = True


@dataclass
class GateDecision:
    action_id: str
    authorised: bool
    reasons: list = field(default_factory=list)   # why it was blocked, if it was
    fired: bool = False                            # whether the effect was allowed to run


def evaluate(
    proposal: ActionProposal,
    classified_by_id: dict,
    agent_consequential_sinks: frozenset,
) -> GateDecision:
    """Authorise or block a consequential action. Fails closed.

    Blocked (not authorised) if the sink is consequential for this agent AND the
    proposal consumes, as an ACTION, any parameter that is an untrusted-derived,
    action-critical value. Otherwise authorised. The check inspects the wiring and the
    computed labels, never the parameter's content.
    """
    reasons: list[str] = []

    sink_is_consequential = proposal.sink in agent_consequential_sinks

    for param_id, mode in proposal.consumes.items():
        if mode != CONSUME_ACTION:
            continue  # consuming as inert data is always fine (describe, not obey)
        c: ClassifiedAssertion | None = classified_by_id.get(param_id)
        if c is None:
            # A parameter with no classified provenance is unknown-origin. Fail closed:
            # we cannot confirm it is safe to act on, so we do not authorise.
            reasons.append(
                f"parameter {param_id!r} consumed as ACTION has no known provenance; "
                f"fail closed"
            )
            continue
        untrusted_derived = c.trust_level == "trust:TAINTED"
        if sink_is_consequential and untrusted_derived and c.action_critical:
            reasons.append(
                f"consequential sink {proposal.sink!r} consumes untrusted-derived, "
                f"action-critical value {param_id!r} (type {c.type_name}) as an ACTION "
                f"instruction"
            )

    authorised = not reasons
    return GateDecision(action_id=proposal.action_id, authorised=authorised, reasons=reasons)


class Actuator:
    """A mock actuator, mirroring the PoC. Records effects instead of performing them,
    so a test can confirm that a blocked action's effect never ran."""

    def __init__(self) -> None:
        self.action_effects: list[str] = []
        self.inert_effects: list[str] = []

    def reset(self) -> None:
        self.action_effects.clear()
        self.inert_effects.clear()


def enforce(
    proposal: ActionProposal,
    classified_by_id: dict,
    agent_consequential_sinks: frozenset,
    actuator: Actuator,
) -> GateDecision:
    """Evaluate the gate and, only if authorised, let the effect run. A blocked action
    never reaches the actuator: the gate fires before the effect, exactly as the PoC's
    gate blocked the payment actuator before any mock money moved."""
    decision = evaluate(proposal, classified_by_id, agent_consequential_sinks)
    if not decision.authorised:
        return decision  # fired stays False; the effect never runs
    for param_id, mode in proposal.consumes.items():
        if mode == CONSUME_ACTION:
            actuator.action_effects.append(f"{proposal.action_id}: acted on {param_id}")
        else:
            actuator.inert_effects.append(f"{proposal.action_id}: logged {param_id}")
    decision.fired = True
    return decision
