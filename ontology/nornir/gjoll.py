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
4, sink-wiring honesty). What Gjoll adds here is that the action-critical determination
is now computed by reachability, not self-asserted per sink.

Two dishonest-declaration seams are now narrowed (D89, the two halves of the root seam
5.1 fix; scoping in `plans/declaration_attestation_scoping.md`):

- Direction B (in `sink_declaration.py`): sink consequentiality is DERIVED from a
  declared effect primitive over an attested table, not read from a per-sink boolean, so
  an author cannot mark a money-moving sink non-consequential to disarm the gate.
- Direction A (below): a value consumed as CONSUME_INERT that flow reachability has
  ALREADY proved action-critical, at a consequential sink, no longer silently passes. An
  inert claim that contradicts the derived reachability is blocked, because the inert
  declaration must not be trusted over the flow graph. Inert only passes unchecked when
  the value is not action-critical.

Both RELOCATE trust rather than remove it (a sink that declares the WRONG effect
primitive is still defeated; that is the C/D follow-on). The gate contains no model on
any of these paths (invariant 3.1): the derivation is set membership over an authored
table and the A check reads the already-computed action-critical label.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .assertions import ClassifiedAssertion
from .effect_probe import EffectObservation, verify_declaration
from .sink_declaration import (
    SinkRegistry,
    effective_consequential,
    validate_proposal,
)


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
    sink_registry: "SinkRegistry | None" = None,
    effect_observations: "dict | None" = None,
) -> GateDecision:
    """Authorise or block a consequential action. Fails closed.

    Blocked (not authorised) if the sink is consequential for this agent AND the
    proposal consumes, as an ACTION, any parameter that is an untrusted-derived,
    action-critical value. Otherwise authorised. The check inspects the wiring and the
    computed labels, never the parameter's content.

    When `sink_registry` is supplied (D84, wiring D81), the proposal is first VALIDATED
    against the declared sink contracts, and a validation failure is a BLOCK, not a
    warning. This closes the three fail-open paths D81 named: an undeclared or mistyped
    sink no longer silently disables the gate (it is treated as consequential), a
    silently-omitted or phantom parameter is caught, and an invalid consume mode is not
    read as inert. Without a registry the gate keeps its prior behaviour, so existing
    callers are unaffected; a real deployment always supplies one.

    When `effect_observations` is supplied (D93, direction D), it maps a sink id to an
    `EffectObservation` recorded by a behavioural probe. The gate cross-checks the sink's
    DECLARED effect primitive against its OBSERVED behaviour and, if the observation shows
    the sink is consequential (whatever the declaration claims), treats it as consequential.
    This closes the wrong-primitive seam B relocated: a money mover that declares itself
    `display_only` passes B's derivation but is caught here by observation. It only ever
    RAISES consequentiality (a fail-closed OR with B's derived answer), so an honest
    non-consequential sink with a clean observation stays ungated; and no observation for a
    sink means D adds nothing (it defers to B), so the parameter is backward-compatible.
    """
    reasons: list[str] = []

    if sink_registry is not None:
        # Fail-closed declaration validation runs BEFORE the content gate. A declaration
        # error is an authorisation failure by itself: we do not gate a proposal we
        # cannot even validate against a known sink contract.
        known_ids = frozenset(classified_by_id.keys())
        validation = validate_proposal(
            proposal.sink, proposal.consumes, sink_registry, known_ids
        )
        if not validation.valid:
            return GateDecision(
                action_id=proposal.action_id,
                authorised=False,
                reasons=list(validation.errors),
            )
        # Consequential status with the fail-closed inversion: an undeclared sink is
        # consequential (we cannot know it is safe), a declared sink follows agent
        # scoping (D24). validate_proposal already blocked an undeclared sink above, so
        # this reads the declared/agent-scoped answer for a valid proposal.
        sink_is_consequential = effective_consequential(
            proposal.sink, sink_registry, agent_consequential_sinks
        )
    else:
        sink_is_consequential = proposal.sink in agent_consequential_sinks

    # D93, direction D: if a behavioural observation exists for this sink, verify the declared
    # effect primitive against it and OR the verified-consequential verdict in. This is a
    # fail-closed raise, never a lower: observation can only make a sink consequential (catching
    # a dishonest inert primitive B trusted), it cannot make an intrinsically consequential sink
    # inert. So B and D compose: whichever proves consequentiality wins, and neither can be
    # disarmed by the other.
    if effect_observations is not None:
        observation = effect_observations.get(proposal.sink)
        if observation is not None:
            declaration = (
                sink_registry.get(proposal.sink) if sink_registry is not None else None
            )
            verification = verify_declaration(declaration, observation)
            if verification.verified_consequential:
                sink_is_consequential = True

    for param_id, mode in proposal.consumes.items():
        c: ClassifiedAssertion | None = classified_by_id.get(param_id)

        if mode != CONSUME_ACTION:
            # A: the fail-closed consume mode (D89, direction A). Consuming a value as inert
            # data is normally fine (describe, not obey), and that is still the common case.
            # But a declaration of CONSUME_INERT on a value that flow reachability has ALREADY
            # proved action-critical, at a consequential sink, is a claim that CONTRADICTS the
            # flow graph: the value can reach a consequential effect, yet the sink declares it
            # will not act on it. That is exactly the dishonest-inert-mode seam (5.1). We do not
            # trust the inert claim over the derived reachability; we block and let review
            # settle it. An inert declaration only passes unchecked when the value is NOT
            # action-critical (so the inert claim cannot be laundering a live path). This is a
            # fail-closed default, not a blacklist: inert on an action-critical value must be
            # EARNED by the value being non-reachable, never granted by the declaration alone.
            if c is None:
                continue  # not action-critical (no provenance to make it so); genuinely inert
            untrusted_derived = c.trust_level == "trust:TAINTED"
            if sink_is_consequential and untrusted_derived and c.action_critical:
                reasons.append(
                    f"consequential sink {proposal.sink!r} declares untrusted-derived, "
                    f"action-critical value {param_id!r} (type {c.type_name}) as CONSUME_INERT, "
                    f"which contradicts its flow reachability to a consequential effect; the "
                    f"inert claim is not trusted over the derived action-critical status "
                    f"(fail closed, D89-A)"
                )
            continue

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
    sink_registry: "SinkRegistry | None" = None,
    effect_observations: "dict | None" = None,
) -> GateDecision:
    """Evaluate the gate and, only if authorised, let the effect run. A blocked action
    never reaches the actuator: the gate fires before the effect, exactly as the PoC's
    gate blocked the payment actuator before any mock money moved. `sink_registry`, when
    supplied, runs the D81 fail-closed declaration validation before the gate (D84).
    `effect_observations`, when supplied, feeds the D93 direction-D behavioural cross-check
    (declared vs observed effect primitive) into the consequentiality determination."""
    decision = evaluate(
        proposal, classified_by_id, agent_consequential_sinks, sink_registry,
        effect_observations,
    )
    if not decision.authorised:
        return decision  # fired stays False; the effect never runs
    for param_id, mode in proposal.consumes.items():
        if mode == CONSUME_ACTION:
            actuator.action_effects.append(f"{proposal.action_id}: acted on {param_id}")
        else:
            actuator.inert_effects.append(f"{proposal.action_id}: logged {param_id}")
    decision.fired = True
    return decision
