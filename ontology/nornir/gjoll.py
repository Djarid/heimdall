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

A named, NARROWED residual of the NO-registry fallback (D97, narrowed by D100). When
`sink_registry` is supplied, `sink_is_consequential` is DERIVED (D89-B) and cannot be
disarmed by a hollow or mismatched `agent_consequential_sinks` argument at THIS call.
Without one, `sink_is_consequential` is now derived from the classify-time
consequential-sink stamp each consumed parameter carries
(`ClassifiedAssertion.consequential_sinks_at_classify`, set by `engine.run` from the
RESOLVED agent context that produced the same value's `action_critical` label), not
from the raw membership test against this call's `agent_consequential_sinks` argument.
A value carrying no stamp at all (`None`, always a hand-built `ClassifiedAssertion`) is
treated fail-closed as consequential. This closes the WIDE residual this docstring
previously described here, that any no-registry gate call was disarmable by a hollow or
swapped `agent_consequential_sinks` argument of its own (see
`ontology/tests/control_surface_harness.py`, D97 then D100).

What this does NOT close. The stamp carries NO NEW TRUST ROOT: it is engine output on
exactly the same footing as `action_critical` and `trust_level`, both of which the gate
already trusts. A caller able to rewrite `classified_by_id` in process, and with it the
stamp, can still disarm this branch, exactly as it already could rewrite those two
fields; that is an integrity assumption the gate makes today, not one D100 introduces.
Closing THAT needs an attested `AgentContext` threaded through the classify-time and
gate-time calls so the sink set cannot be swapped between them in process (a materially
larger change touching every caller's signature). That is a named, triggered follow-on
for its own decision, not built here. The registry-supplied path is unaffected and
remains the closed, recommended way to call this gate.
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
    # Non-blocking audit signal (D100). Today's only entry is a divergence between the
    # classify-time stamp union and the `agent_consequential_sinks` argument on the
    # no-registry branch. A note NEVER affects `authorised`: a caller may legitimately
    # narrow the set at gate time, so blocking on a mismatch would be friction without
    # safety.
    notes: list = field(default_factory=list)


def _consequential_from_stamps(
    proposal: ActionProposal,
    classified_by_id: dict,
    agent_consequential_sinks: frozenset,
) -> "tuple[bool, list[str]]":
    """Derive `sink_is_consequential` for the NO-REGISTRY branch of `evaluate` from the
    classify-time stamps carried by the consumed parameters (D100), returning the
    verdict and any non-blocking audit notes.

    Three cases, considered over the CLASSIFIED CONSUMED PARAMETERS: the entries named
    in `proposal.consumes` that resolve to a non-None entry in `classified_by_id`. A
    parameter absent from `classified_by_id` entirely contributes nothing here; it is
    handled by the pre-existing per-parameter fail-closed rule in `evaluate`'s main
    loop and does not by itself trigger case 2 below (EC-3: an absent entry is a
    different condition from a present entry carrying no stamp).

      Case 2 (decided FIRST): any classified consumed parameter carries NO stamp
        (`is None`) -> fail closed, `sink_is_consequential = True`. This is decided
        before any union is taken, so one unstamped parameter cannot be outvoted by
        stamped siblings.
      Case 1 (otherwise): every classified consumed parameter carries a stamp -> the
        UNION of those stamps is the source of truth; `agent_consequential_sinks` is
        NOT consulted for consequentiality. A divergence between the union and the
        supplied argument is recorded as a non-blocking note, never a reason: a caller
        may legitimately narrow its sink set at gate time.
      Case 3: there are no classified consumed parameters at all -> unchanged from
        pre-D100, `proposal.sink in agent_consequential_sinks`.

    The predicate stays `proposal.sink in <set>` in cases 1 and 3; only the PROVENANCE
    of <set> changes. This is why D100 cannot introduce friction the pre-D100 code did
    not already have, and why it is structurally not the rejected fix that ORed a
    value's `action_critical` flag into a question about whether THIS sink is
    consequential (D97)."""
    stamps: list = []
    for param_id in proposal.consumes:
        c = classified_by_id.get(param_id)
        if c is None:
            continue
        stamps.append(c.consequential_sinks_at_classify)

    if not stamps:
        # Case 3: no classified consumed parameters at all. Unchanged from pre-D100.
        return proposal.sink in agent_consequential_sinks, []

    if any(stamp is None for stamp in stamps):
        # Case 2: at least one classified consumed parameter carries no stamp. Fail
        # closed, decided BEFORE any union is taken.
        return True, []

    # Case 1: every classified consumed parameter carries a stamp.
    union: frozenset = frozenset().union(*stamps)
    sink_is_consequential = proposal.sink in union
    notes: list[str] = []
    if union != agent_consequential_sinks:
        notes.append(
            f"D100: the classify-time consequential-sink union {sorted(union)!r} "
            f"differs from the agent_consequential_sinks argument "
            f"{sorted(agent_consequential_sinks)!r} supplied at this gate call; the "
            f"stamp is authoritative for consequentiality and the argument was not "
            f"consulted"
        )
    return sink_is_consequential, notes


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

    Named residual (D97, narrowed by D100): without `sink_registry`,
    `sink_is_consequential` is now derived from the classify-time consequential-sink
    stamp carried by the consumed parameters (`consequential_sinks_at_classify`),
    unioned when every classified consumed parameter carries one and failed closed when
    any does not, so an empty or mismatched `agent_consequential_sinks` argument at
    THIS call no longer disarms the block below. What remains: the stamp is engine
    output on the same footing as `action_critical` and `trust_level`, so a caller able
    to rewrite `classified_by_id` in process can still rewrite the stamp too and disarm
    the branch, exactly as it already could for those two fields. See the module
    docstring's "named, NARROWED residual" section for detail. Always supply
    `sink_registry` for a real deployment.
    """
    reasons: list[str] = []
    notes: list[str] = []

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
        # D100: derive from the classify-time stamp carried by the consumed
        # parameters rather than from the raw membership test against this call's
        # agent_consequential_sinks argument, which had no independent source of
        # truth to check itself against. The registry branch above is authoritative
        # and is NOT touched by this; the stamp must never be read on that path.
        sink_is_consequential, stamp_notes = _consequential_from_stamps(
            proposal, classified_by_id, agent_consequential_sinks
        )
        notes.extend(stamp_notes)

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
    return GateDecision(
        action_id=proposal.action_id, authorised=authorised, reasons=reasons, notes=notes
    )


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
