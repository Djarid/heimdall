"""D97/D100: the control-surface ceiling-enforcement gap, and the gjoll no-registry
residual (now narrowed by D100, not fixed by D97).

Two claims from a read-only audit (`.opencode/plans/bifrost-secure-autonomous-harness-
brainstorm.md`, finding F4), each checked here before being trusted, in the mandatory
negative-control spirit D93/D94/D95/D96 each applied to their own gap:

1. `control_surface.resolve()`'s docstring claimed the trust ceiling is enforced against
   silent escalation; the body was literally `return agent`, performing no check at all.
   `run_ceiling_enforcement` reproduces the PRE-FIX body inline (`_unfixed_resolve`) to
   prove the old code really did let an escalating override through, then proves the
   real (post-fix) `resolve()` clamps it, and that an honest, non-escalating override
   still passes through untouched (no friction).

2. `gjoll.evaluate`/`gjoll.enforce`'s no-registry fallback computed `sink_is_
   consequential` as the raw membership test `proposal.sink in agent_consequential_
   sinks`, with nothing to check that argument against (D97). D100 changes WHICH copy of
   the consequential-sink set the no-registry branch consults: it now derives from the
   classify-time stamp `engine.run` binds to each value (`ClassifiedAssertion.
   consequential_sinks_at_classify`), failing closed when a value carries no stamp at
   all, rather than from the unbound `agent_consequential_sinks` argument supplied at
   THIS call. `run_gjoll_no_registry_residual` proves three things, in the mandatory
   negative-control spirit: the closed case is genuinely closed (AC-1), the closure is
   structurally NOT the rejected `action_critical`-ORing fix D97 examined (AC-2, the
   decisive control), and an attested-empty stamp behaves as present-and-empty, never as
   absent (AC-3). It also proves the registry path (D89-B) is untouched (AC-11, AC-12)
   and reports the narrower residual that survives: a caller able to rewrite the
   classify-time stamp (or `action_critical`, or `trust_level`) in process, before the
   gate call, is out of the threat model, exactly as it already is for those two labels.
   D100 does NOT claim item (b) of D97 is closed, only narrowed; `AgentContext`
   attestation (Approach B, D97's item (c)) is a named, triggered follow-on, not built
   here.
"""

from __future__ import annotations

import sys

from ontology.yggdrasil.control_surface import AgentContext, GLOBAL_DEFAULT, resolve
from ontology.nornir.assertions import ClassifiedAssertion
from ontology.nornir import Nornir, MarshalledAssertion
from ontology.nornir.gjoll import ActionProposal, Actuator, evaluate, enforce, CONSUME_ACTION
from ontology.nornir.sink_declaration import (
    SinkDeclaration,
    SinkRegistry,
    MOVE_MONEY,
    DISPLAY_ONLY,
)


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


def _try_check(rep: Report, msg: str, fn) -> None:
    """Run `fn()`, expecting a bool. On ANY exception (in particular an AttributeError
    reading `ClassifiedAssertion.consequential_sinks_at_classify` or `GateDecision.
    notes`, or a TypeError constructing a `ClassifiedAssertion` with a
    `consequential_sinks_at_classify=` keyword, before D100 lands and adds these
    fields) report that as a failure too, with the exception surfaced, rather than
    letting one missing field crash the whole suite. This lets every acceptance
    criterion be observed individually, pre-D100, failing for ITS OWN right reason
    (a wrong authorisation outcome, or a not-yet-existent field), per the spec's
    section 10.2 build-order requirement."""
    try:
        ok = fn()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this IS the check
        rep.check(False, f"{msg} [raised {type(exc).__name__}: {exc}]")
        return
    rep.check(bool(ok), msg)


def _build_f_honest() -> tuple["AgentContext", "ClassifiedAssertion"]:
    """F-honest (spec section 5's preamble). An agent with ONE real consequential
    sink, one value whose flow reaches it, run through the REAL `nornir.run` so the
    stamp (once D100 lands) and `action_critical` are produced by the pipeline itself,
    never assumed by a hand-built fixture that would beg the very question AC-1, AC-2
    and AC-3 exist to answer (the spec is explicit that this matters: a closed-case
    check built on a fixture that assumes its own conclusion is not evidence)."""
    agent = AgentContext(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({"sink:payments.execute"}),
    )
    marshalled = MarshalledAssertion(
        "money.value",
        "taint:EXTERNAL_COMMS",
        {
            "subject_extracted": "transfer",
            "requested_action_summary": "wire transfer the funds to the supplier account",
        },
        flows=("sink:payments.execute",),
    )
    from ontology.yggdrasil import load

    result = Nornir(load()).run([marshalled], agent=agent)
    return agent, result.by_id("money.value")


def _build_f_readonly() -> tuple["AgentContext", "ClassifiedAssertion"]:
    """F-readonly (spec section 5's preamble). An agent with NO consequential sinks at
    all, one informational, non-flowing value, run through the real engine so the
    attested-EMPTY stamp (frozenset(), present) is produced by the pipeline, not
    asserted by hand. This is the fixture the empty-versus-absent distinction (C-c,
    REQ-2) is load-bearing for."""
    agent = AgentContext(agent_id="readonly", consequential_sinks=frozenset())
    marshalled = MarshalledAssertion(
        "note",
        "taint:EXTERNAL_COMMS",
        {
            "subject_extracted": "fyi",
            "requested_action_summary": "for your information, no action needed",
        },
    )
    from ontology.yggdrasil import load

    result = Nornir(load()).run([marshalled], agent=agent)
    return agent, result.by_id("note")


def _build_f_handbuilt() -> "ClassifiedAssertion":
    """F-handbuilt (spec section 5's preamble). A `ClassifiedAssertion` constructed
    directly, never through `nornir.run`, exactly as this file's ORIGINAL residual
    reproduction did before this rewrite: no classify-time provenance of any kind.
    This is what a caller that never ran the value through the engine at all looks
    like, and it is the fixture REQ-6 case 2 (fail closed on an absent stamp) is
    tested against."""
    c = ClassifiedAssertion(
        assertion_id="mal.value",
        type_name="comms:money_move_request",
        actionable=False,
        trust_level="trust:TAINTED",
        taint_class="taint:EXTERNAL_COMMS",
        fields={},
    )
    c.action_critical = True  # already proven reachable to a real sink elsewhere
    return c


def _check_ac1_closed_case(rep: Report, f_honest) -> None:
    agent, c = f_honest
    proposal = ActionProposal(
        "ac1-pay", "sink:payments.execute", {c.assertion_id: CONSUME_ACTION},
        declared_safe=False,
    )
    actuator = Actuator()

    def _fn() -> bool:
        d = enforce(proposal, {c.assertion_id: c}, frozenset(), actuator)
        return (not d.authorised) and (not d.fired) and not actuator.action_effects

    _try_check(
        rep,
        "AC-1 (REQ-6 case 1, REQ-17) THE CLOSED CASE: F-honest at its real "
        "consequential sink, gated with a HOLLOWED agent_consequential_sinks "
        "argument and no sink_registry, must be BLOCKED before firing. Today this "
        "authorises and fires; this is the criterion that must flip from pass to "
        "fail when D100 is reverted",
        _fn,
    )


def _check_ac2_inert_sink_control(rep: Report, f_honest) -> None:
    agent, c = f_honest
    proposal = ActionProposal(
        "ac2-audit", "sink:audit_log", {c.assertion_id: CONSUME_ACTION},
        declared_safe=True,
    )
    actuator = Actuator()

    def _fn() -> bool:
        d = enforce(proposal, {c.assertion_id: c}, frozenset(), actuator)
        return d.authorised and d.fired

    _try_check(
        rep,
        "AC-2 (REQ-18, REQ-8) MANDATORY CONTROL, the decisive one: F-honest's "
        "action-critical value at an honestly inert, unrelated sink (sink:"
        "audit_log, absent from the stamp) must still be AUTHORISED. This is the "
        "criterion the rejected action_critical-ORing fix D97 examined would "
        "FAIL, and it is more discriminating than AC-3",
        _fn,
    )


def _check_ac3_empty_stamp_no_friction(rep: Report, f_readonly) -> None:
    agent, c = f_readonly
    proposal = ActionProposal(
        "ac3-harmless", "sink:harmless", {c.assertion_id: CONSUME_ACTION},
        declared_safe=True,
    )
    actuator = Actuator()

    def _fn() -> bool:
        d = enforce(proposal, {c.assertion_id: c}, frozenset(), actuator)
        return d.authorised and d.fired

    _try_check(
        rep,
        "AC-3 (REQ-18, REQ-2) MANDATORY CONTROL, the empty-stamp no-friction "
        "control: F-readonly's attested-EMPTY stamp (present, frozenset()) must "
        "behave as present-and-empty, never as absent -- authorised at an "
        "unrelated sink with no sink_registry",
        _fn,
    )


def _check_ac4_absence_vs_emptiness(rep: Report) -> None:
    sink = "sink:payments.execute"

    def _make(suffix: str, stamp) -> "ClassifiedAssertion":
        c = ClassifiedAssertion(
            assertion_id=f"ac4.{suffix}",
            type_name="comms:money_move_request",
            actionable=False,
            trust_level="trust:TAINTED",
            taint_class="taint:EXTERNAL_COMMS",
            fields={},
            consequential_sinks_at_classify=stamp,
        )
        c.action_critical = True
        return c

    def _fn() -> bool:
        empty_c = _make("empty", frozenset())
        none_c = _make("none", None)
        empty_prop = ActionProposal("ac4-empty", sink, {empty_c.assertion_id: CONSUME_ACTION})
        none_prop = ActionProposal("ac4-none", sink, {none_c.assertion_id: CONSUME_ACTION})
        d_empty = evaluate(empty_prop, {empty_c.assertion_id: empty_c}, frozenset())
        d_none = evaluate(none_prop, {none_c.assertion_id: none_c}, frozenset())
        return d_empty.authorised and (not d_none.authorised)

    _try_check(
        rep,
        "AC-4 (REQ-2): absence (None) and emptiness (frozenset()) on the SAME "
        "input shape must produce OPPOSITE outcomes -- frozenset() authorises "
        "(not absent), None fails closed. A single implementation returning the "
        "same answer for both has conflated them",
        _fn,
    )


def _check_ac5_ac22_fail_closed_absent_stamp(rep: Report, f_handbuilt) -> bool:
    """AC-5 and AC-22 are the same underlying claim (the spec's own table names them
    as the general Given/When/Then and its specific call-site restatement
    respectively): F-handbuilt, no stamp at all, gated with no registry, must now be
    blocked fail closed. Returns whether it blocked, so the residual-reporting
    function below can describe the surviving, narrower gap honestly rather than
    re-deriving this outcome a second time."""
    proposal = ActionProposal(
        "ac5-pay", "sink:payments.execute", {f_handbuilt.assertion_id: CONSUME_ACTION},
        declared_safe=False,
    )
    outcome = {"blocked": None}

    def _fn() -> bool:
        d = evaluate(proposal, {f_handbuilt.assertion_id: f_handbuilt}, frozenset())
        outcome["blocked"] = not d.authorised
        return outcome["blocked"]

    _try_check(
        rep,
        "AC-5 / AC-22 (REQ-6 case 2, REQ-19, REQ-17): F-handbuilt (NO classify-"
        "time provenance at all) gated with no sink_registry must be NOT "
        "authorised, fail closed. Today this authorises and is the recorded "
        "residual; this is the call site control_surface_harness.py line 170 "
        "reproduced, rewritten around the intended change",
        _fn,
    )
    return outcome["blocked"]


def _check_ac6_unstamped_not_outvoted(rep: Report, f_honest) -> None:
    agent, honest_c = f_honest  # stamp = {"sink:payments.execute"}; "sink:unrelated" absent
    handbuilt = ClassifiedAssertion(
        assertion_id="ac6.handbuilt",
        type_name="comms:money_move_request",
        actionable=False,
        trust_level="trust:TAINTED",
        taint_class="taint:EXTERNAL_COMMS",
        fields={},
    )
    handbuilt.action_critical = True
    proposal = ActionProposal(
        "ac6-unrelated",
        "sink:unrelated",
        {honest_c.assertion_id: CONSUME_ACTION, handbuilt.assertion_id: CONSUME_ACTION},
    )

    def _fn() -> bool:
        d = evaluate(
            proposal,
            {honest_c.assertion_id: honest_c, handbuilt.assertion_id: handbuilt},
            frozenset(),
        )
        return not d.authorised

    _try_check(
        rep,
        "AC-6 (REQ-6 case 2): one unstamped consumed parameter (hand-built, no "
        "stamp) must NOT be outvoted by a stamped sibling (F-honest) whose OWN "
        "stamp excludes the sink -- case 2 fires and blocks, decided BEFORE any "
        "union is taken",
        _fn,
    )


def _check_ac7_union_widens_conjunct_binds(rep: Report) -> None:
    def _make(assertion_id: str, stamp, action_critical: bool) -> "ClassifiedAssertion":
        c = ClassifiedAssertion(
            assertion_id=assertion_id,
            type_name="comms:money_move_request",
            actionable=False,
            trust_level="trust:TAINTED",
            taint_class="taint:EXTERNAL_COMMS",
            fields={},
            consequential_sinks_at_classify=stamp,
        )
        c.action_critical = action_critical
        return c

    def _fn_blocks() -> bool:
        a = _make("ac7.a", frozenset({"sink:a"}), action_critical=True)
        b = _make("ac7.b", frozenset({"sink:b"}), action_critical=False)
        proposal = ActionProposal(
            "ac7-block", "sink:b",
            {a.assertion_id: CONSUME_ACTION, b.assertion_id: CONSUME_ACTION},
        )
        d = evaluate(proposal, {a.assertion_id: a, b.assertion_id: b}, frozenset())
        return not d.authorised

    def _fn_authorises() -> bool:
        a = _make("ac7.a2", frozenset({"sink:a"}), action_critical=False)
        b = _make("ac7.b2", frozenset({"sink:b"}), action_critical=False)
        proposal = ActionProposal(
            "ac7-ok", "sink:b",
            {a.assertion_id: CONSUME_ACTION, b.assertion_id: CONSUME_ACTION},
        )
        d = evaluate(proposal, {a.assertion_id: a, b.assertion_id: b}, frozenset())
        return d.authorised

    _try_check(
        rep,
        "AC-7a (REQ-6 case 1, union semantics): the union of two stamps "
        "({sink:a} and {sink:b}) widens sink_is_consequential to include "
        "sink:b even though neither parameter's OWN stamp alone forces it "
        "consequential via the OTHER parameter, and the decision blocks because "
        "one consumed parameter is itself tainted and action-critical",
        _fn_blocks,
    )
    _try_check(
        rep,
        "AC-7b (REQ-6 case 1, union semantics): the SAME widened union must NOT "
        "bypass the per-parameter conjunct -- when no consumed parameter is "
        "itself action-critical, the decision IS authorised",
        _fn_authorises,
    )


def _check_ac8_no_classified_params_unchanged(rep: Report) -> None:
    """AC-8 (REQ-6 case 3): with zero classified consumed parameters, this is
    unrelated to D100 and must be identical before and after: sink_is_consequential
    reverts to the untouched raw membership test, and the PRE-EXISTING per-parameter
    fail-closed rule (predates D100 entirely) still blocks a CONSUME_ACTION parameter
    with no known provenance. This is a control: it should PASS both before and
    after D100, exactly like AC-2, AC-3 and AC-11."""
    proposal = ActionProposal(
        "ac8-ghost", "sink:nowhere-in-any-set", {"ghost.param": CONSUME_ACTION},
    )

    def _fn() -> bool:
        d = evaluate(proposal, {}, frozenset())
        return (not d.authorised) and any("no known provenance" in r for r in d.reasons)

    _try_check(
        rep,
        "AC-8 (REQ-6 case 3) CONTROL: zero classified consumed parameters leaves "
        "behaviour EXACTLY pre-D100 -- the pre-existing 'no known provenance' "
        "fail-closed rule still blocks, unrelated to any stamp",
        _fn,
    )


def _check_ac9_mismatch_note(rep: Report, f_honest) -> None:
    agent, c = f_honest  # stamp union = {"sink:payments.execute"}
    proposal = ActionProposal(
        "ac9-audit", "sink:audit_log", {c.assertion_id: CONSUME_ACTION}, declared_safe=True,
    )

    def _fn_mismatch() -> bool:
        d = evaluate(proposal, {c.assertion_id: c}, frozenset())
        return d.authorised and (not d.reasons) and len(d.notes) == 1

    def _fn_match() -> bool:
        d = evaluate(proposal, {c.assertion_id: c}, agent.consequential_sinks)
        return len(d.notes) == 0

    def _fn_registry() -> bool:
        registry = SinkRegistry()
        registry.declare(
            SinkDeclaration(
                name="sink:audit_log",
                parameters=frozenset({c.assertion_id}),
                consequential_by_default=False,
                effect_primitive=DISPLAY_ONLY,
            )
        )
        d = evaluate(proposal, {c.assertion_id: c}, frozenset(), sink_registry=registry)
        return len(d.notes) == 0

    _try_check(
        rep,
        "AC-9a (REQ-10): on a union/argument MISMATCH (case 1), the decision "
        "records exactly one non-blocking note naming both sets; authorised "
        "stays True and reasons stays empty (a note can never block)",
        _fn_mismatch,
    )
    _try_check(
        rep,
        "AC-9b (REQ-10): when the union and the supplied argument are EQUAL, "
        "notes is empty",
        _fn_match,
    )
    _try_check(
        rep,
        "AC-9c (REQ-10): on the REGISTRY path, notes is always empty (the stamp "
        "branch is never reached at all)",
        _fn_registry,
    )


def _check_ac10_stamp_identity_and_additive(rep: Report) -> None:
    from ontology.yggdrasil import load

    def _fn_object_identity() -> bool:
        agent = AgentContext(
            agent_id="canonical-agent",
            trust_ceiling="CANONICAL",
            consequential_sinks=frozenset({"sink:x"}),
        )
        marshalled = MarshalledAssertion(
            "ac10.value", "taint:EXTERNAL_COMMS", {"subject_extracted": "x"},
            flows=("sink:x",),
        )
        result = Nornir(load()).run([marshalled], agent=agent)
        c = result.by_id("ac10.value")
        resolved = resolve(agent)
        return (
            c.consequential_sinks_at_classify == resolved.consequential_sinks
            and c.consequential_sinks_at_classify is resolved.consequential_sinks
        )

    def _fn_none_agent() -> bool:
        marshalled = MarshalledAssertion(
            "ac10.none_agent", "taint:EXTERNAL_COMMS", {"subject_extracted": "x"},
        )
        result = Nornir(load()).run([marshalled], agent=None)
        c = result.by_id("ac10.none_agent")
        return (
            c.consequential_sinks_at_classify == GLOBAL_DEFAULT.consequential_sinks
            and c.consequential_sinks_at_classify is not None
        )

    def _fn_additive_optional() -> bool:
        c = ClassifiedAssertion(
            assertion_id="ac10.additive",
            type_name="x",
            actionable=False,
            trust_level="trust:TAINTED",
            taint_class="taint:EXTERNAL_COMMS",
            fields={},
        )
        return c.consequential_sinks_at_classify is None

    _try_check(
        rep,
        "AC-10a (REQ-3, REQ-4, REQ-5): the stamp on an engine.run-produced value "
        "equals resolve(agent).consequential_sinks AND IS the same object "
        "(identity, not just equality -- one shared immutable reference)",
        _fn_object_identity,
    )
    _try_check(
        rep,
        "AC-10b (REQ-3): agent=None stamps GLOBAL_DEFAULT.consequential_sinks "
        "(frozenset(), present) rather than None",
        _fn_none_agent,
    )
    _try_check(
        rep,
        "AC-10c (REQ-1): a ClassifiedAssertion built with NO "
        "consequential_sinks_at_classify argument at all still constructs, and "
        "the field reads None (additive, optional; all six existing "
        "construction sites keep working unedited)",
        _fn_additive_optional,
    )


def _check_ac11_registry_path_untouched(rep: Report, f_handbuilt) -> None:
    c = f_handbuilt
    proposal = ActionProposal(
        "ac11-pay", "sink:payments.execute", {c.assertion_id: CONSUME_ACTION},
        declared_safe=False,
    )
    actuator = Actuator()
    registry = SinkRegistry()
    registry.declare(
        SinkDeclaration(
            name="sink:payments.execute",
            parameters=frozenset({c.assertion_id}),
            consequential_by_default=True,
            effect_primitive=MOVE_MONEY,
        )
    )

    def _fn() -> bool:
        d = enforce(proposal, {c.assertion_id: c}, frozenset(), actuator, sink_registry=registry)
        reason_text = " ".join(d.reasons).lower()
        no_stamp_language = "stamp" not in reason_text and "provenance stamp" not in reason_text
        return (not d.authorised) and (not d.fired) and no_stamp_language

    _try_check(
        rep,
        "AC-11 (REQ-7, REQ-20) MANDATORY CONTROL: F-handbuilt (no stamp at all) "
        "on the WITH-registry path is still blocked by D89-B's derived "
        "consequentiality, and the block reason names the ordinary consumption "
        "reason, never an absent-stamp reason -- the registry branch reaches its "
        "verdict WITHOUT consulting the stamp at all",
        _fn,
    )


def _check_ac12_stamp_not_ored_into_registry(rep: Report) -> None:
    sink = "sink:display_panel"

    def _fn() -> bool:
        # Fixture construction moved INSIDE _fn (was previously built directly in
        # the function body, ahead of and outside _try_check's try/except): the
        # ClassifiedAssertion(...) call below is exactly the one that raises
        # TypeError pre-D100 (consequential_sinks_at_classify is not yet a
        # constructor keyword), and it must be caught and reported as THIS
        # check's own FAIL line, not allowed to propagate out of
        # run_gjoll_no_registry_residual and abort every check after it.
        c = ClassifiedAssertion(
            assertion_id="ac12.value",
            type_name="comms:money_move_request",
            actionable=False,
            trust_level="trust:TAINTED",
            taint_class="taint:EXTERNAL_COMMS",
            fields={},
            consequential_sinks_at_classify=frozenset({sink}),
        )
        c.action_critical = True
        proposal = ActionProposal(
            "ac12-display", sink, {c.assertion_id: CONSUME_ACTION}, declared_safe=True,
        )
        registry = SinkRegistry()
        registry.declare(
            SinkDeclaration(
                name=sink,
                parameters=frozenset({c.assertion_id}),
                consequential_by_default=False,
                effect_primitive=DISPLAY_ONLY,
            )
        )
        d = evaluate(proposal, {c.assertion_id: c}, frozenset(), sink_registry=registry)
        return d.authorised

    _try_check(
        rep,
        "AC-12 (REQ-7): a stamp that DOES contain the sink must NOT be ORed into "
        "the registry derivation -- an honestly display_only-declared sink stays "
        "AUTHORISED even though the value's own stamp claims the sink is "
        "consequential (an agent may legitimately list an honestly-inert sink in "
        "consequential_sinks; D89-B's derivation, not the stamp, decides here)",
        _fn,
    )


def _report_narrowed_residual(rep: Report, f_handbuilt, none_stamp_blocked) -> None:
    """REQ-19: keep printing [RESIDUAL, RECORDED] (or the anti-drift [NOTE]) so a
    future change is reported honestly rather than absorbed silently, exactly as
    D97's reporting-without-failing discipline requires -- but with NARROWED wording.
    The None-stamp case above (AC-5/AC-22) is checked as an ordinary pass/fail
    criterion; this function's job is only to describe, honestly and mechanically,
    the DIFFERENT, narrower gap that survives regardless of whether that case is
    fixed: a caller able to rewrite the classify-time stamp in process, before the
    gate call (EC-8), which this build does not claim to close and is out of scope
    on exactly the footing action_critical and trust_level already carry."""
    forged = ClassifiedAssertion(
        assertion_id="residual.forged",
        type_name="comms:money_move_request",
        actionable=False,
        trust_level="trust:TAINTED",
        taint_class="taint:EXTERNAL_COMMS",
        fields={},
    )
    forged.action_critical = True  # already proven reachable to a real sink elsewhere
    forged_proposal = ActionProposal(
        "residual-forged-stamp", "sink:payments.execute",
        {forged.assertion_id: CONSUME_ACTION}, declared_safe=False,
    )
    try:
        # Simulate EC-8: a caller that already controls the process rewrites the
        # stamp to look attested-empty on a value it ALREADY knows is action-critical
        # for the real sink. Setting this attribute directly on the instance (rather
        # than via the constructor) is deliberate: it stands in for "in process,
        # after the engine produced the value", which is precisely what EC-8 names.
        forged.consequential_sinks_at_classify = frozenset()
        d_forged = evaluate(forged_proposal, {forged.assertion_id: forged}, frozenset())
        forged_authorises = d_forged.authorised
    except Exception as exc:  # pragma: no cover - reported, not swallowed
        forged_authorises = None
        rep.line(
            f"  [CRITICAL] could not even evaluate the forged-stamp residual "
            f"reproduction: {type(exc).__name__}: {exc}"
        )

    if forged_authorises:
        closed_case_phrase = (
            "is now blocked fail closed (D100)"
            if none_stamp_blocked
            else "is NOT YET blocked (pre-D100 state; see AC-5/AC-22 above)"
        )
        rep.line(
            f"  [RESIDUAL, RECORDED] a value carrying NO classify-time provenance "
            f"at all (the None-stamp case, AC-5/AC-22) {closed_case_phrase}. The "
            f"gap that SURVIVES regardless is narrower: a caller able to rewrite "
            f"consequential_sinks_at_classify on a ClassifiedAssertion in process, "
            f"before the gate call, still disarms the no-registry branch (here "
            f"reproduced by forging an attested-empty stamp on a value already "
            f"known action-critical). This is NOT MITIGATED and is out of the "
            f"threat model, exactly as it already is for action_critical and "
            f"trust_level (D94's identity-versus-honesty limit). This build does "
            f"NOT claim the no-registry path is disarmable by its OWN gate-time "
            f"argument any more (that is the closed case, D100's whole point); "
            f"only this narrower, in-process gap remains, and AgentContext "
            f"attestation (D97's item (c)) is a named, triggered follow-on that "
            f"would not close it either (attestation binds identity, never "
            f"honesty)."
        )
    elif forged_authorises is False:
        rep.line(
            "  [NOTE] the in-process label-rewrite residual no longer reproduces "
            "(a forged, attested-empty stamp on an already action-critical value "
            "is now blocked too); if this was deliberate, update D100's decision "
            "text and this harness's wording (do not let this drift silently)."
        )
    else:
        rep.line(
            "  [NOTE] the forged-stamp residual reproduction could not be "
            "evaluated at all (see the CRITICAL line above); that is itself "
            "worth investigating, not absorbing."
        )
    rep.line("")


def run_gjoll_no_registry_residual(rep: Report) -> None:
    """D100 (REQ-17 to REQ-20): the gjoll no-registry fallback, rewritten around the
    classify-time stamp. Replaces the single pre-D100 check with the closed case
    (AC-1), the two mandatory anti-friction/anti-conflation controls that prove this
    is NOT the rejected action_critical-ORing fix (AC-2, AC-3), the absence-versus-
    emptiness distinction (AC-4), the fail-closed and union semantics (AC-5 to AC-8),
    the non-blocking audit note (AC-9), the stamp's identity and additivity (AC-10),
    and the registry path's continued isolation (AC-11, AC-12), before reporting the
    narrower residual that survives (REQ-19)."""
    rep.line("=== D100: gjoll's no-registry fallback, derived from the classify-time "
             "stamp (REQ-17 to REQ-20) ===")

    f_honest = _build_f_honest()
    f_readonly = _build_f_readonly()
    f_handbuilt = _build_f_handbuilt()

    _check_ac1_closed_case(rep, f_honest)
    _check_ac2_inert_sink_control(rep, f_honest)
    _check_ac3_empty_stamp_no_friction(rep, f_readonly)
    _check_ac4_absence_vs_emptiness(rep)
    none_stamp_blocked = _check_ac5_ac22_fail_closed_absent_stamp(rep, f_handbuilt)
    _check_ac6_unstamped_not_outvoted(rep, f_honest)
    _check_ac7_union_widens_conjunct_binds(rep)
    _check_ac8_no_classified_params_unchanged(rep)
    _check_ac9_mismatch_note(rep, f_honest)
    _check_ac10_stamp_identity_and_additive(rep)
    _check_ac11_registry_path_untouched(rep, f_handbuilt)
    _check_ac12_stamp_not_ored_into_registry(rep)

    _report_narrowed_residual(rep, f_handbuilt, none_stamp_blocked)


def run_run_control_surface_wording(rep: Report) -> None:
    """AC-31 (REQ-21). `ontology.tests.harness`'s `run_control_surface` docstring and
    its `[PASS]` summary string (lines 747 to 772, OUTSIDE the D10 block at 530 to
    685, which REQ-14 requires stay byte-identical and which this function never
    reads or edits) must state the residual in its NARROWED, post-D100 form and must
    not carry the wider, pre-D100 claim that the no-registry path is disarmable by
    its own gate-time argument. Made mechanical rather than left to prose review: it
    reads the live source text of that one function and asserts the narrowed wording
    is present and the wider wording is absent. Today (pre-D100) this fails: `harness.
    py` still carries the wider claim word for word."""
    import inspect
    from ontology.tests import harness as _harness_module

    rep.line("=== AC-31 (REQ-21): run_control_surface's residual wording is narrowed ===")

    source = inspect.getsource(_harness_module.run_control_surface)

    wide_claim_present = (
        "closed only when a sink_registry is supplied" in source
        or "disarms it" in source
    )
    narrowed_provenance_phrase = "no reachability provenance" in source
    narrowed_rewrite_phrase = (
        "label-rewrite" in source
        or ("rewrite" in source and "process" in source)
    )

    rep.check(
        not wide_claim_present,
        "AC-31a: run_control_surface's docstring/summary must NOT carry the "
        "wider, pre-D100 claim that an empty/mismatched agent_consequential_"
        "sinks argument disarms the no-registry path (today it still does; this "
        "must flip to pass once REQ-21's rewrite lands)",
    )
    rep.check(
        narrowed_provenance_phrase and narrowed_rewrite_phrase,
        "AC-31b: run_control_surface's docstring/summary must name the "
        "NARROWED residual explicitly (a value carrying no reachability "
        "provenance at all, plus the in-process label-rewrite assumption)",
    )
    rep.line("")


def main() -> int:
    rep = Report()
    run_ceiling_enforcement(rep)
    run_gjoll_no_registry_residual(rep)
    run_run_control_surface_wording(rep)
    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} critical finding(s).")
        return 1
    print(
        "SUITE PASS: resolve() clamps a ceiling-escalating override, an honest "
        "override still passes through untouched, the gjoll no-registry branch "
        "derives consequentiality from the classify-time stamp and fails closed on "
        "an absent one (D100), the registry path remains untouched, and the "
        "narrower, in-process-rewrite residual that survives is checked and "
        "recorded."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
