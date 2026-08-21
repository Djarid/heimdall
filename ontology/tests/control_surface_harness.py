"""D97: the control-surface ceiling-enforcement gap, and the gjoll no-registry residual.

Two claims from a read-only audit (`.opencode/plans/bifrost-secure-autonomous-harness-
brainstorm.md`, finding F4), each checked here before being trusted, in the mandatory
negative-control spirit D93/D94/D95/D96 each applied to their own gap:

1. `control_surface.resolve()`'s docstring claimed the trust ceiling is enforced against
   silent escalation; the body was literally `return agent`, performing no check at all.
   `run_ceiling_enforcement` reproduces the PRE-FIX body inline (`_unfixed_resolve`) to
   prove the old code really did let an escalating override through, then proves the
   real (post-fix) `resolve()` clamps it, and that an honest, non-escalating override
   still passes through untouched (no friction).

2. `gjoll.evaluate`/`gjoll.enforce`'s no-registry fallback computes
   `sink_is_consequential` as the raw membership test `proposal.sink in
   agent_consequential_sinks`, with nothing to check that argument against. An empty or
   mismatched `agent_consequential_sinks` at the GATE call disarms the check regardless
   of the parameter's already-computed `action_critical` status. `run_gjoll_no_registry_
   residual` demonstrates this is CLOSED when a `sink_registry` is supplied (D89-B
   derives consequentiality from the effect primitive, independent of the raw
   membership test) and OPEN, and left open on purpose, without one. This is recorded as
   an honest, bounded, named residual (D97), not a fresh failure: it composes with the
   false-inert red bar's own "leave the real gap visible" discipline rather than
   smoothing it over. Closing it would need requiring a registry unconditionally
   (breaking backward compatibility with every existing no-registry caller, including
   this repository's own D10 mandatory safe/unsafe proof in `harness.py`) or threading
   an attested `AgentContext` through every gate call (a materially larger change); both
   are named follow-ons in D97's decision text, not built here.
"""

from __future__ import annotations

import sys

from ontology.yggdrasil.control_surface import AgentContext, GLOBAL_DEFAULT, resolve
from ontology.nornir.assertions import ClassifiedAssertion
from ontology.nornir.gjoll import ActionProposal, Actuator, evaluate, enforce, CONSUME_ACTION
from ontology.nornir.sink_declaration import SinkDeclaration, SinkRegistry, MOVE_MONEY


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    def line(self, s: str) -> None:
        self.lines.append(s)

    def check(self, ok: bool, msg: str) -> None:
        if ok:
            self.line(f"  [PASS] {msg}")
        else:
            self.failures += 1
            self.line(f"  [CRITICAL] {msg}")

    def dump(self) -> None:
        print("\n".join(self.lines))


def _unfixed_resolve(agent: "AgentContext | None") -> "AgentContext":
    """A literal reproduction of `control_surface.resolve()`'s ORIGINAL body (pre-D97),
    kept here only so this harness can demonstrate what the code actually did before the
    fix, rather than asserting the gap from the read-only audit alone."""
    if agent is None:
        return GLOBAL_DEFAULT
    return agent


def run_ceiling_enforcement(rep: Report) -> None:
    rep.line("=== D97a: control_surface.resolve() must not silently escalate the trust ceiling ===")
    escalated = AgentContext(agent_id="attacker", trust_ceiling="CANONICAL")

    # Prove the PRE-FIX behaviour actually let this through.
    pre_fix = _unfixed_resolve(escalated)
    rep.check(
        pre_fix.trust_ceiling == "CANONICAL",
        "pre-fix reproduction: an unbounded resolve() lets an override raise the "
        "ceiling to CANONICAL, above the global default's TAINTED (confirms the "
        "read-only audit's claim reproduces as a real gap, not merely a docstring "
        "mismatch)",
    )

    # The fix: the real resolve() must clamp.
    post_fix = resolve(escalated)
    rep.check(
        post_fix.trust_ceiling == GLOBAL_DEFAULT.trust_ceiling,
        f"resolve() clamps an escalating override to the global default's ceiling "
        f"({GLOBAL_DEFAULT.trust_ceiling!r}), not the agent's claimed "
        f"({escalated.trust_ceiling!r})",
    )

    # Control: an override at or below the global default's ceiling must pass through
    # unclamped. D24's whole point is that an agent MAY be narrower than the default;
    # gating that would be friction without safety.
    honest = AgentContext(
        agent_id="honest", trust_ceiling="TAINTED", consequential_sinks=frozenset({"sink:x"})
    )
    passthrough = resolve(honest)
    rep.check(
        passthrough is honest,
        "resolve() does not touch an override that does not escalate the ceiling "
        "(no friction on a legitimately-scoped agent)",
    )

    # Control: None still resolves to the global default unchanged.
    rep.check(
        resolve(None) is GLOBAL_DEFAULT,
        "resolve(None) still returns the global default unchanged",
    )

    # Fail closed on an unranked/unknown ceiling string: it must not be treated as if it
    # ranked low just because this module cannot place it on the lattice.
    unknown = AgentContext(agent_id="unknown-level", trust_ceiling="NOT_A_REAL_LEVEL")
    clamped_unknown = resolve(unknown)
    rep.check(
        clamped_unknown.trust_ceiling == GLOBAL_DEFAULT.trust_ceiling,
        "an unrecognised trust_ceiling string is not trusted as if it ranked low; it is "
        "clamped to the global default (fail closed on an unranked value)",
    )
    rep.line("")


def run_gjoll_no_registry_residual(rep: Report) -> None:
    """D97b: the gjoll no-registry fallback's honest, named residual. Not a regression
    fixed here; see the D97 decision text and the module docstrings in `gjoll.py`. Checks
    both halves so the claim is verified, not merely asserted."""
    rep.line("=== D97b: gjoll's no-registry fallback residual (named, not fixed here) ===")

    c = ClassifiedAssertion(
        assertion_id="mal.value",
        type_name="comms:money_move_request",
        actionable=False,
        trust_level="trust:TAINTED",
        taint_class="taint:EXTERNAL_COMMS",
        fields={},
    )
    c.action_critical = True  # already proven reachable to a real sink elsewhere

    proposal = ActionProposal(
        action_id="pay-exploit",
        sink="sink:payments.execute",
        consumes={"mal.value": CONSUME_ACTION},
        declared_safe=False,
    )
    actuator = Actuator()

    # WITH a registry: D89-B derives consequentiality from the declared effect
    # primitive, so a hollow agent_consequential_sinks argument cannot disarm it.
    registry = SinkRegistry()
    registry.declare(
        SinkDeclaration(
            name="sink:payments.execute",
            parameters=frozenset({"mal.value"}),
            consequential_by_default=True,
            effect_primitive=MOVE_MONEY,
        )
    )
    d_with = enforce(
        proposal, {"mal.value": c}, frozenset(), actuator, sink_registry=registry
    )
    rep.check(
        (not d_with.authorised) and (not d_with.fired),
        "WITH a sink_registry, an empty/hollow agent_consequential_sinks does NOT "
        "disarm the gate (D89-B's derived consequentiality already covers this)",
    )

    # WITHOUT a registry: no other source of truth exists, so the same hollow argument
    # disarms the gate. This is the honest residual, recorded, not a fresh failure.
    actuator.reset()
    d_without = evaluate(proposal, {"mal.value": c}, agent_consequential_sinks=frozenset())
    if d_without.authorised:
        rep.line(
            "  [RESIDUAL, RECORDED] WITHOUT a sink_registry, an empty/hollow "
            "agent_consequential_sinks authorises an action-critical, "
            "untrusted-derived ACTION consumption at a real consequential sink. This "
            "is the named, bounded residual of the no-registry fallback (D97): "
            "closing it needs a registry (backward-compatibility cost, named callers "
            "in D97) or an attested AgentContext threaded through the call (a larger, "
            "separately-scoped follow-on), so it is documented rather than patched "
            "here."
        )
    else:
        # If a future change closes this without a registry, that is good news, but it
        # must be a deliberate, recorded decision, not a silent side effect.
        rep.line(
            "  [NOTE] the no-registry residual no longer reproduces; if this was "
            "deliberate, update D97's text (do not let this drift silently)."
        )
    rep.line("")


def main() -> int:
    rep = Report()
    run_ceiling_enforcement(rep)
    run_gjoll_no_registry_residual(rep)
    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} critical finding(s).")
        return 1
    print(
        "SUITE PASS: resolve() clamps a ceiling-escalating override, an honest override "
        "still passes through untouched, and the gjoll no-registry residual is checked "
        "and recorded (closed with a sink_registry, present without one)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
