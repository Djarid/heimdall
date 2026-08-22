"""The control surface: per-agent binding. NOT part of the ontology (D20).

This is deliberately separate from Yggdrasil. The ontology holds action and
constraint VOCABULARY; the control surface holds the per-agent BINDING that selects
from that vocabulary (D20, `ONTOLOGY_CONSTRUCTION.md` 2.3). Which actions an agent
may perform, which constraints bind it and its trust ceiling are per-agent and do
not belong in the type tree. Keeping them here, in the same package but a distinct
module, makes the ontology-versus-control-surface line physical.

Two orthogonal axes (D21): by-domain lives in the ontology, by-agent lives here. An
agent spans domains; a domain is touched by many agents. This module is per-agent.

Phase 1 grants no consequential capability: the action-critical set is empty and
the machinery is dormant (`ONTOLOGY_CONSTRUCTION.md` 4.1). The point of building it
now is the attach discipline: the schema to declare and gate consequential actions
exists and is exercised by tests (which supply their own agent contexts with their
own sinks, agent-scoped per D24), so arming it later is a config change, not a
build. An agent can never grant itself a permission above its trust ceiling.

Action-critical status is agent-scoped (D24): a value is action-critical for an
agent iff it can reach a sink in THAT agent's reachable sink set. So the sinks live
on the agent context, not globally. The loaded ontology ships no armed sinks; a
test or a later phase supplies them per agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .spine.trust import TRUST_ORDER


@dataclass(frozen=True)
class AgentContext:
    """One agent's control-surface binding.

    `permitted_actions` are action-type names (from the ontology's action
    vocabulary) this agent may perform. `trust_ceiling` is the highest trust level
    this agent may assign or hold; it can never exceed it. `consequential_sinks` are
    the sink node names that are consequential FOR THIS AGENT: the target set
    flow-to-sink reachability propagates back from (D24). An empty set is the Phase 1
    default, and means nothing is action-critical for this agent.
    """

    agent_id: str
    permitted_actions: frozenset[str] = frozenset()
    trust_ceiling: str = "TAINTED"
    consequential_sinks: frozenset[str] = frozenset()
    # D103, appended last so no positional construction anywhere is disturbed
    # and every existing construction site keeps working unedited (REQ-8).
    # Both default None, exactly as D94's SinkDeclaration pair does, so
    # verification is enforced only where a caller opts in.
    #
    #   authoriser  = the identity that attested this agent binding
    #   attestation = the keyed digest over this binding's canonical bytes
    #
    # An unattested context is REFUSED only when a TrustedAuthoriserSet is
    # supplied to resolve(). With no trusted set nothing is verified, which is
    # the named opt-in residual (REQ-30 limit 1), reported live by the
    # invocation detector (REQ-18, ontology/tests/agentcontext_attestation_
    # harness.py's run_req18_invocation_boundary_detector).
    authoriser: "str | None" = None
    attestation: "str | None" = None

    def may_perform(self, action_name: str) -> bool:
        return action_name in self.permitted_actions

    def record_type(self) -> str:
        """D103 (REQ-9). This binding's attested-record type tag, as the
        shared substrate's own constant, never a duplicated literal (AC-12):
        a future rename of the constant cannot leave a stale literal behind
        here. Imported function-locally and relatively (REQ-16): a module-
        level import of `authorisation_record` here would create a real
        circular-import failure, because `ontology/nornir/__init__.py`
        imports `.engine`, which imports `AgentContext` and `resolve` from
        THIS module -- so importing `ontology.yggdrasil.control_surface`
        before `ontology.nornir` (as `control_surface_harness.py` already
        does) would trigger that chain against a partially initialised
        module. `SinkRegistry.declare_attested` carries the same deferred
        import for the same reason."""
        from ..nornir.authorisation_record import RECORD_TYPE_AGENT_CONTEXT

        return RECORD_TYPE_AGENT_CONTEXT

    def canonical_fields(self) -> "tuple[tuple[str, str], ...]":
        """D103 (REQ-9). The attested CONTENT of this binding: `agent_id`,
        `permitted_actions` (sorted), `trust_ceiling`, `consequential_sinks`
        (sorted) and `authoriser`. `attestation` is deliberately absent: it is
        the digest being computed or checked, not part of what it covers.

        `authoriser` IS covered, precisely because it is not on the same
        footing as `attestation`. `attestation` cannot cover itself (it is the
        value being computed), but `authoriser` names WHO is attesting, and an
        attestation minted under authoriser A must not verify when the record
        is later presented naming authoriser B, even where B is ALSO trusted
        and even where A and B happen to share one secret (D94's own reason
        for putting `authoriser` in the canonical bytes: relying solely on
        per-authoriser secret distinctness degenerates to nothing the moment
        two trusted authorisers share a secret). Because `authoriser` is
        covered, it must be part of the record BEFORE `compute_record_
        attestation` is called, not attached afterwards: a fixture or caller
        that computes the digest first and assigns `authoriser` second has
        built an inherently unverifiable record, which is a fixture bug, not
        evidence that `authoriser` should be excluded here.

        `trust_ceiling` is encoded as an OPAQUE STRING. This deliberately
        does NOT decide whether it draws from the assertion trust lattice
        (`TRUST_ORDER`) or a distinct agent-authority scale -- that question
        stays OPEN (REQ-32, D97's own note, and see `_trust_rank`'s
        docstring for the same wording discipline applied there)."""
        return (
            ("agent_id", self.agent_id),
            ("permitted_actions", ",".join(sorted(self.permitted_actions))),
            ("trust_ceiling", self.trust_ceiling),
            ("consequential_sinks", ",".join(sorted(self.consequential_sinks))),
            ("authoriser", self.authoriser or ""),
        )


# The global default control surface (HEIMDALL.md design principle 5). Agent-level
# overrides take precedence for that agent only, bounded by the agent's trust
# ceiling. The Phase 1 default grants only the read-only, human-gated actions and no
# consequential sinks: the action-critical set is empty.
GLOBAL_DEFAULT = AgentContext(
    agent_id="__global_default__",
    permitted_actions=frozenset(
        {"action:classify", "action:triage", "action:summarise", "action:draft_for_review"}
    ),
    trust_ceiling="TAINTED",
    consequential_sinks=frozenset(),
)


def _trust_rank(level: str) -> int:
    """Rank a `trust_ceiling` string against the trust lattice ordering (`TRUST_ORDER`,
    `spine/trust.py`), low to high. This is the ONLY ordering defined anywhere in the
    codebase today, and `trust_ceiling` values already use its literal names
    ("TAINTED" and so on), so this fix uses it without resolving the separate, still-open
    question of whether `AgentContext.trust_ceiling` should instead draw from a distinct
    agent-authority scale (recorded as an open question elsewhere, not decided here; see
    D97's note). An unrecognised level is not on the lattice at all, so it cannot be
    ranked as low: it is treated as maximally escalated, fail closed, so a string this
    module cannot place never earns a bypass by being unrankable."""
    try:
        return TRUST_ORDER.index(level)
    except ValueError:
        return len(TRUST_ORDER)


def resolve(
    agent: AgentContext | None,
    trusted: "TrustedAuthoriserSet | None" = None,
) -> AgentContext:
    """Resolve the effective control surface for an agent: the global default unless
    an agent-level override is supplied. An override may not raise the trust ceiling
    above the global default's in Phase 1 (an agent cannot grant itself a permission
    above its ceiling); we enforce the ceiling is not silently escalated (D97: this
    enforcement was previously undocumented in name only, `resolve` returned `agent`
    unmodified and performed no check at all).

    Fails closed: an override whose `trust_ceiling` ranks ABOVE the global default's is
    refused, not silently honoured. Refusal here means CLAMPING the effective ceiling
    down to the global default's, not raising, so a caller that already validated
    everything else about the agent still gets a usable context back, one that can no
    longer exceed what the docstring already promised. An override at or below the
    global default's ceiling passes through untouched: this must never be friction on a
    legitimately-scoped agent narrowing itself.

    D103, the integrity check. When `trusted` is supplied (an optional trailing
    `TrustedAuthoriserSet`, `None` by default) the binding's attestation is
    verified BEFORE the ceiling clamp, and an unattested, unknown-authoriser or
    altered binding RAISES `ValueError` rather than degrading. With `trusted`
    omitted (the default), this function is BYTE-IDENTICAL to its pre-D103
    behaviour: no verification, no new failure mode, only the D97 clamp. This is
    what keeps `engine.py`'s existing `resolve(agent)` call, and every other
    existing caller, working unedited.

    Why it raises instead of returning a narrowed context (REQ-12). The control
    surface's fail-closed direction is NOT UNIFORM across its fields. Clamping
    `trust_ceiling` down and emptying `permitted_actions` both NARROW capability,
    so degrading is safe there. Emptying `consequential_sinks` DISARMS the
    action-critical determination, because an empty set means nothing is
    action-critical: that is exactly the hollowing attack this check exists to
    catch. Returning `GLOBAL_DEFAULT` on a refusal -- whose `consequential_sinks`
    IS empty -- would therefore turn a detected tamper into a disarmed surface,
    handing an attacker exactly the value the tamper was trying to install. So a
    refusal denies the caller a surface at all, raising rather than degrading, on
    `SinkRegistry.declare_attested`'s refuse-at-load precedent (D94). No `return`
    in this function is ever reached as the consequence of a verification
    failure.

    Verification precedes the clamp (REQ-13). When the clamp then fires on an
    HONESTLY attested but escalating context, the returned, derived context's
    content no longer matches its original digest, so the clamped return clears
    the attested pair (`authoriser=None, attestation=None`) rather than carrying
    a stale one: a later re-verification of a clamped context is therefore
    refused on the ACCURATE, unattested path (case one below), never on a
    misleading tampered path. An honestly attested, NON-escalating context passes
    through untouched, with its attested pair intact (REQ-15, EC-6): attestation
    must never be friction on a legitimately-scoped agent.

    `agent is None` returns `GLOBAL_DEFAULT` with NO verification, always (REQ-14):
    it is a module constant on the authorisation path, not a caller-supplied
    input, and it is a NAMED TRUST ROOT on the same footing as this code -- an
    unattested caller-supplied context is never admitted, but `GLOBAL_DEFAULT`
    is not that; anyone able to edit it can edit `resolve()` in the same file.
    `GLOBAL_DEFAULT` carries no authoriser and no digest.

    This closes the CEILING check (D97) and the IDENTITY/INTEGRITY check (D103)
    of the `AgentContext` binding. It does not attest that the binding's content
    is TRUE: a trusted authoriser who honestly attests a hollow
    `consequential_sinks` set produces a perfectly valid attestation of a
    disarmed surface (REQ-30 limit 2, D94's own identity-versus-honesty limit,
    reproduced here for the agent binding). Enforcement is opt-in: with `trusted`
    omitted, nothing is checked (REQ-30 limit 1). And a caller that rewrites a
    `ClassifiedAssertion`'s stamp downstream, in process, after `resolve` has
    verified, is untouched (D100's EC-8, REQ-30 limit 3). None of these three
    limits is closed here; each is named so a future reader does not read D103
    as closing item (c) of D97 in full."""
    if agent is None:
        return GLOBAL_DEFAULT
    if trusted is not None:
        from ..nornir.authorisation_record import verify_record_attestation

        result = verify_record_attestation(agent, trusted)
        if not result.verified:
            raise ValueError(result.reason)
    if _trust_rank(agent.trust_ceiling) > _trust_rank(GLOBAL_DEFAULT.trust_ceiling):
        # The clamp DERIVES a new object, so its content no longer matches its
        # digest. Clear the attested pair rather than carry a stale one (REQ-13):
        # a re-verification must refuse it as UNATTESTED (accurate), not as
        # TAMPERED (misleading -- this was a legitimate clamp, not a tamper).
        return replace(
            agent,
            trust_ceiling=GLOBAL_DEFAULT.trust_ceiling,
            authoriser=None,
            attestation=None,
        )
    return agent
