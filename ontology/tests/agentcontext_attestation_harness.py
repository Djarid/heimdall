"""D103's own suite: `AgentContext`'s integrity is enforced at `resolve()` (REQ-23, REQ-24).

Run from the repo root:

    python -m ontology.tests.agentcontext_attestation_harness

Why a NEW file, not an extension of `control_surface_harness.py` (REQ-23). That suite
already owns D97's ceiling-clamp claim and D100's no-registry-stamp claim; a third
decision's assertions in the same file would make a future failure ambiguous about
which mechanism regressed (Single Responsibility, section 7.3). This file is not
edited into that one, and does not edit `control_surface.py`, `engine.py`,
`harness.py` or `control_surface_harness.py` itself: it tests the CONTRACT this
build adds, from outside, exactly as `sink_attestation_harness.py` tests D94's
declaration-attestation contract without editing `sink_declaration.py`.

The mandatory-negative-control-first discipline (D93 to D97, D101's synthetic-
ontology precedent), applied here. `run_ac14_gap_reproduction` is written and must be
observed to PASS *before* the fix is trusted: a literal inline copy of TODAY's
`resolve()` body (`_unattested_resolve`, on `control_surface_harness.py`'s own
`_unfixed_resolve` precedent) is shown to let a hollowed `consequential_sinks` set
flow, unchanged, through the REAL `Nornir.run` and a REAL money-sink `gjoll.evaluate`
call with NO `sink_registry`, to an AUTHORISED decision. This uses ONLY features that
exist today (no new `AgentContext` fields, no `trusted=` parameter anywhere), so it is
not testing the fix; it is proving the gap the fix exists to close.

Every check from that point on exercises the REAL `resolve(agent, trusted)` and
therefore imports symbols that DO NOT EXIST YET: `AgentContext(authoriser=...,
attestation=...)`, `Nornir.run(..., trusted=...)`, and
`ontology.nornir.authorisation_record`'s `compute_record_attestation`,
`verify_record_attestation` and `RECORD_TYPE_AGENT_CONTEXT`. Running this file before
D103 lands is EXPECTED to fail: most checks catch a `TypeError` (an unexpected
keyword argument) or an `ImportError`/`ModuleNotFoundError` (the not-yet-built
substrate module) INDIVIDUALLY, via `_try_check`, so a missing feature is reported as
THAT check's own `[FAIL]` line rather than aborting every check after it
(`control_surface_harness.py`'s own `_try_check` precedent, applied here to D103's
not-yet-built surface, exactly as that file's comments describe doing for D100).

The three honesty obligations (REQ-30), each a MANDATORY LIMIT, not a caveat left in
prose: `run_ac23_residual_opt_in_survives` (enforcement is opt-in; nothing opts in
today), `run_ac24_residual_trusted_lie_disarms` (attestation binds identity and
integrity, never honesty; D94's obligation five, reproduced here for the agent
binding), and `run_ac25_residual_label_rewrite_untouched` (D100's EC-8, the in-process
label rewrite, is explicitly out of this build's threat model). Each prints
`[RESIDUAL, RECORDED]` when the limit reproduces as expected, and an anti-drift
`[NOTE]` if it does not, so a future change that closes one of these is REPORTED
rather than silently absorbed (D97's and D100's own reporting-without-failing
discipline).

The REQ-18 invocation-boundary detector (`run_req18_invocation_boundary_detector`)
reuses `gjoll_invocation_harness.py`'s OWN helpers (`_iter_repo_python_files`,
`_call_target`, `_is_test_path`) rather than writing a second detector mechanism, on
the same allowlist polarity `ALLOWED_IMPORT_ROOTS` and `NON_TEST_ALLOWLIST` both use
(D71, D96): a non-test call site supplying a trusted set must be EARNED by a
reviewed, allowlisted entry, never granted by silence.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from ontology.yggdrasil.control_surface import AgentContext, GLOBAL_DEFAULT, resolve, _trust_rank
from ontology.nornir import Nornir, MarshalledAssertion
from ontology.nornir.gjoll import ActionProposal, evaluate, CONSUME_ACTION
from ontology.nornir.sink_declaration import SinkDeclaration, SinkRegistry, MOVE_MONEY
from ontology.nornir.sink_attestation import TrustedAuthoriser, TrustedAuthoriserSet


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    def line(self, s: str = "") -> None:
        self.lines.append(s)

    def check(self, ok: bool, label: str) -> None:
        if ok:
            self.line(f"  [PASS] {label}")
        else:
            self.failures += 1
            self.line(f"  [FAIL] {label}")

    def dump(self) -> None:
        print("\n".join(self.lines))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _try_check(rep: Report, msg: str, fn) -> None:
    """Run `fn()`, expecting a bool. On ANY exception (a `TypeError` constructing
    `AgentContext` with `authoriser=`/`attestation=` before REQ-8 lands, a `TypeError`
    from `resolve`'s/`Nornir.run`'s not-yet-existent `trusted=` parameter, or an
    `ImportError`/`ModuleNotFoundError` for the not-yet-existent
    `ontology.nornir.authorisation_record` module) report that as a failure too, with
    the exception surfaced, rather than letting one missing feature crash the whole
    suite (`control_surface_harness.py`'s own `_try_check` precedent, applied here to
    D103's not-yet-built surface)."""
    try:
        ok = fn()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this IS the check
        rep.check(False, f"{msg} [raised {type(exc).__name__}: {exc}]")
        return
    rep.check(bool(ok), msg)


PLATFORM_SECRET = b"agentcontext-attestation-platform-secret-not-in-any-context"
TRUSTED_AUTHORISER_ID = "ops-authoriser"
MONEY_SINK = "sink:payments.execute"


def _unattested_resolve(agent: "AgentContext | None") -> "AgentContext":
    """A literal inline copy of `control_surface.resolve()`'s CURRENT (pre-D103) body
    -- the D97 ceiling clamp, and nothing else -- on `control_surface_harness.py`'s
    `_unfixed_resolve` precedent (AC-14, REQ-24). Kept here so this harness
    demonstrates what the code actually does TODAY, rather than merely asserting the
    gap from the spec's prose. Uses the real, imported `_trust_rank`, because trust
    ranking itself is untouched by this build; only the ABSENCE of any attestation
    check is what this copy is reproducing."""
    if agent is None:
        return GLOBAL_DEFAULT
    if _trust_rank(agent.trust_ceiling) > _trust_rank(GLOBAL_DEFAULT.trust_ceiling):
        return replace(agent, trust_ceiling=GLOBAL_DEFAULT.trust_ceiling)
    return agent


def _build_hollowed_plain() -> AgentContext:
    """A hollowed AgentContext built with ONLY today's existing fields. AC-14's
    reproduction must use nothing this build adds, so the demonstration is of the gap
    as it exists NOW, before any fix."""
    return AgentContext(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset(),  # hollowed: nothing is action-critical
    )


def _build_escalated_plain() -> AgentContext:
    return AgentContext(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="CANONICAL",
        consequential_sinks=frozenset({MONEY_SINK}),
    )


def _run_gate_no_registry(agent: "AgentContext | None", sink: str = MONEY_SINK, trusted=None):
    """Run one marshalled money-flow assertion through the REAL `Nornir.run` under
    `agent` (optionally with `trusted`, once REQ-17 lands), then gate the resulting
    classified value at `sink` through `gjoll.evaluate` with NO `sink_registry`. This
    is the exact AC-14/AC-24 shape: D100's classify-time stamp is what the
    no-registry branch actually consults, so the reproduction exercises the real
    pipeline end to end rather than a hand-built `ClassifiedAssertion` that would beg
    the question."""
    from ontology.yggdrasil import load

    marshalled = MarshalledAssertion(
        "money.value",
        "taint:EXTERNAL_COMMS",
        {
            "subject_extracted": "transfer",
            "requested_action_summary": "wire transfer the funds to the supplier account",
        },
        flows=(sink,),
    )
    onto = load()
    if trusted is None:
        result = Nornir(onto).run([marshalled], agent=agent)
    else:
        result = Nornir(onto).run([marshalled], agent=agent, trusted=trusted)
    c = result.by_id("money.value")
    proposal = ActionProposal(
        "gate-check", sink, {c.assertion_id: CONSUME_ACTION}, declared_safe=False,
    )
    agent_sinks = agent.consequential_sinks if agent is not None else frozenset()
    return evaluate(proposal, {c.assertion_id: c}, agent_sinks)


def run_ac14_gap_reproduction(rep: Report) -> None:
    """AC-14, REQ-24. BEFORE trusting the fix, reproduce the gap using ONLY features
    that exist TODAY (no new AgentContext fields, no trusted= parameter anywhere): a
    hollowed context flows through `_unattested_resolve` unchanged and, run through
    the real `Nornir.run` and gated at a real money sink through `gjoll.evaluate`
    with NO sink_registry, the decision is AUTHORISED. An escalated context IS
    clamped by D97 (that half is not open), but nothing asks who supplied the
    escalation -- the forged PROVENANCE, not the ceiling value, is what remains
    undetected, and this check states that distinction rather than claiming the
    ceiling half was ever open after D97."""
    rep.line("=== AC-14 (REQ-24): the gap, reproduced BEFORE the fix is trusted ===")

    hollowed = _build_hollowed_plain()
    pre_fix_hollowed = _unattested_resolve(hollowed)
    rep.check(
        pre_fix_hollowed is hollowed and pre_fix_hollowed.consequential_sinks == frozenset(),
        "the pre-fix reproduction returns a hollowed context UNCHANGED -- no "
        "verification of any kind is performed on it today",
    )

    def _fn_hollowed_authorises() -> bool:
        decision = _run_gate_no_registry(pre_fix_hollowed)
        return decision.authorised

    _try_check(
        rep,
        "the hollowed context, run through the REAL Nornir.run and gated at "
        f"{MONEY_SINK} with NO sink_registry, is AUTHORISED today -- the hollowing "
        "really disarms the surface (the finding this build exists to catch, F4)",
        _fn_hollowed_authorises,
    )

    escalated = _build_escalated_plain()
    pre_fix_escalated = _unattested_resolve(escalated)
    rep.check(
        pre_fix_escalated.trust_ceiling == GLOBAL_DEFAULT.trust_ceiling,
        "the pre-fix reproduction of an ESCALATED context: the ceiling half IS "
        "already clamped by D97 -- this build must not claim credit for that half",
    )
    rep.line(
        "  [NOTE] today's resolve() body never asks WHO supplied the escalated "
        "ceiling; the CLAMP is D97's, closed already. The missing PROVENANCE check "
        "-- whether the escalation was even legitimately authored -- is this "
        "build's own finding, and the checks below (resolve(agent, trusted)) test "
        "that half directly, not this reproduction."
    )
    rep.line()


def _build_f_trusted() -> TrustedAuthoriserSet:
    t = TrustedAuthoriserSet()
    t.trust(TrustedAuthoriser(authoriser_id=TRUSTED_AUTHORISER_ID, secret=PLATFORM_SECRET))
    return t


def _build_f_attested() -> AgentContext:
    """F-attested (spec section 5's shared fixtures). Raises whatever the missing
    substrate/field raises today (ImportError for ontology.nornir.authorisation_
    record, or TypeError for AgentContext's not-yet-existent authoriser=/
    attestation= keywords); callers reach this ONLY inside a `_try_check`-wrapped
    closure, so that failure is reported as THAT check's own [FAIL] line, never
    allowed to abort every check after it."""
    from ontology.nornir.authorisation_record import compute_record_attestation

    base = AgentContext(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({MONEY_SINK}),
    )
    digest = compute_record_attestation(base, PLATFORM_SECRET)
    return AgentContext(
        agent_id=base.agent_id,
        permitted_actions=base.permitted_actions,
        trust_ceiling=base.trust_ceiling,
        consequential_sinks=base.consequential_sinks,
        authoriser=TRUSTED_AUTHORISER_ID,
        attestation=digest,
    )


def _build_f_hollowed(f_attested: AgentContext) -> AgentContext:
    """F-hollowed: F-attested with consequential_sinks hollowed and the ORIGINAL
    digest retained -- the disarming attack this build exists to catch."""
    return AgentContext(
        agent_id=f_attested.agent_id,
        permitted_actions=f_attested.permitted_actions,
        trust_ceiling=f_attested.trust_ceiling,
        consequential_sinks=frozenset(),
        authoriser=f_attested.authoriser,
        attestation=f_attested.attestation,
    )


def _build_f_escalated(f_attested: AgentContext) -> AgentContext:
    """F-escalated: F-attested with trust_ceiling raised and the ORIGINAL digest
    retained."""
    return AgentContext(
        agent_id=f_attested.agent_id,
        permitted_actions=f_attested.permitted_actions,
        trust_ceiling="CANONICAL",
        consequential_sinks=f_attested.consequential_sinks,
        authoriser=f_attested.authoriser,
        attestation=f_attested.attestation,
    )


def _fixtures():
    """Build F-trusted, F-attested, F-hollowed and F-escalated fresh, every time,
    inside the CALLER's own `_try_check`-wrapped closure (never at module or
    runner-function scope): a missing field or a missing substrate module must
    surface as THAT check's own [FAIL] line, not abort every check after it
    (`control_surface_harness.py`'s `_fn`-scoped-construction precedent, applied
    here to the new authoriser/attestation fields and the not-yet-existent
    authorisation_record module)."""
    trusted = _build_f_trusted()
    f_attested = _build_f_attested()
    f_hollowed = _build_f_hollowed(f_attested)
    f_escalated = _build_f_escalated(f_attested)
    return trusted, f_attested, f_hollowed, f_escalated


def run_altered_field_refused(rep: Report) -> None:
    """AC-10 (REQ-9, REQ-10), restated at resolve()'s own boundary. Each covered
    field, altered independently with the ORIGINAL (now-stale) digest retained, must
    make resolve(tampered, trusted) raise ValueError. Five sub-checks, one per
    covered field."""
    rep.line(
        "=== A record altered after attestation is REFUSED, independently per "
        "covered field (AC-10) ==="
    )

    def _tamper(f_attested: AgentContext, **overrides) -> AgentContext:
        fields = dict(
            agent_id=f_attested.agent_id,
            permitted_actions=f_attested.permitted_actions,
            trust_ceiling=f_attested.trust_ceiling,
            consequential_sinks=f_attested.consequential_sinks,
            authoriser=f_attested.authoriser,
            attestation=f_attested.attestation,  # the STALE digest, deliberately retained
        )
        fields.update(overrides)
        return AgentContext(**fields)

    def _make_case(overrides: dict):
        def _fn() -> bool:
            trusted, f_attested, _f_hollowed, _f_escalated = _fixtures()
            tampered = _tamper(f_attested, **overrides)
            try:
                resolve(tampered, trusted)
            except ValueError:
                return True
            return False
        return _fn

    cases = [
        ("agent_id", dict(agent_id="attacker")),
        ("permitted_actions", dict(permitted_actions=frozenset({"action:admin"}))),
        ("trust_ceiling", dict(trust_ceiling="CANONICAL")),
        ("consequential_sinks (the hollowing tamper)", dict(consequential_sinks=frozenset())),
        ("authoriser", dict(authoriser="someone-else-also-trusted")),
    ]
    for label, overrides in cases:
        _try_check(
            rep,
            f"altering {label} after attestation makes resolve(tampered, trusted) "
            f"raise ValueError",
            _make_case(overrides),
        )
    rep.line()


def run_ec5_authoriser_is_covered(rep: Report) -> None:
    """EC-5. An attestation minted under authoriser A must not verify when the
    record names authoriser B, EVEN WHERE B IS ALSO TRUSTED: authoriser is a covered
    field, so the canonical bytes differ and the digest cannot match under B's
    secret either. This isolates the refusal to the COVERED-FIELD property, distinct
    from the generic per-field tamper check above (which swaps to an untrusted name
    and so could be explained by either reason)."""
    rep.line(
        "=== EC-5: an authoriser swap is refused because authoriser is a COVERED "
        "field, even when the NAMED authoriser is also trusted ==="
    )

    def _fn() -> bool:
        trusted = _build_f_trusted()
        trusted.trust(
            TrustedAuthoriser(authoriser_id="second-authoriser-also-trusted",
                               secret=b"second-authoriser-secret")
        )
        f_attested = _build_f_attested()
        swapped = AgentContext(
            agent_id=f_attested.agent_id,
            permitted_actions=f_attested.permitted_actions,
            trust_ceiling=f_attested.trust_ceiling,
            consequential_sinks=f_attested.consequential_sinks,
            authoriser="second-authoriser-also-trusted",  # ALSO trusted
            attestation=f_attested.attestation,  # stale digest, minted under ops-authoriser
        )
        try:
            resolve(swapped, trusted)
        except ValueError:
            return True
        return False

    _try_check(
        rep,
        "resolve() refuses a record naming a DIFFERENT, ALSO-TRUSTED authoriser "
        "under the original digest (D94's own reason for covering authoriser: a "
        "valid attestation must not be replayable under a different authoriser id)",
        _fn,
    )
    rep.line()


def run_unknown_authoriser_refused(rep: Report) -> None:
    """AC-3, restated at resolve()'s boundary. A context naming an authoriser absent
    from the trusted set must be refused because the authoriser is UNTRUSTED, not
    because the digest happens to mismatch."""
    rep.line("=== An unknown or forged authoriser is REFUSED ===")

    def _fn() -> bool:
        from ontology.nornir.authorisation_record import compute_record_attestation

        trusted = _build_f_trusted()
        rogue_base = AgentContext(
            agent_id="treasury",
            permitted_actions=frozenset({"action:classify"}),
            trust_ceiling="TAINTED",
            consequential_sinks=frozenset({MONEY_SINK}),
        )
        rogue_digest = compute_record_attestation(rogue_base, b"attacker-chosen-secret")
        rogue = AgentContext(
            agent_id=rogue_base.agent_id,
            permitted_actions=rogue_base.permitted_actions,
            trust_ceiling=rogue_base.trust_ceiling,
            consequential_sinks=rogue_base.consequential_sinks,
            authoriser="attacker",
            attestation=rogue_digest,
        )
        try:
            resolve(rogue, trusted)
        except ValueError as exc:
            reason = str(exc).lower()
            return "not in the trusted" in reason or "unknown" in reason or "untrusted" in reason
        return False

    _try_check(
        rep,
        "resolve(rogue, trusted) raises ValueError naming the untrusted authoriser, "
        "not a digest mismatch",
        _fn,
    )
    rep.line()


def run_unattested_refused_three_shapes(rep: Report) -> None:
    """AC-4, restated at resolve()'s boundary. Silence never earns trust: no
    authoriser, no digest, or neither must all make resolve(agent, trusted) raise
    ValueError."""
    rep.line("=== An unattested context is REFUSED, in all three shapes ===")

    def _make_case(overrides: dict):
        def _fn() -> bool:
            trusted, f_attested, _f_hollowed, _f_escalated = _fixtures()
            fields = dict(
                agent_id=f_attested.agent_id,
                permitted_actions=f_attested.permitted_actions,
                trust_ceiling=f_attested.trust_ceiling,
                consequential_sinks=f_attested.consequential_sinks,
                authoriser=f_attested.authoriser,
                attestation=f_attested.attestation,
            )
            fields.update(overrides)
            rec = AgentContext(**fields)
            try:
                resolve(rec, trusted)
            except ValueError:
                return True
            return False
        return _fn

    shapes = [
        ("no authoriser, digest present", dict(authoriser=None)),
        ("authoriser present, no digest", dict(attestation=None)),
        ("neither", dict(authoriser=None, attestation=None)),
    ]
    for label, overrides in shapes:
        _try_check(
            rep,
            f"a context with {label} makes resolve(agent, trusted) raise "
            f"ValueError (unattested)",
            _make_case(overrides),
        )
    rep.line()


def run_f4_escalations_mandatory(rep: Report) -> None:
    """AC-11. MANDATORY. The two escalations finding F4 names are each caught,
    checked as NAMED, SEPARATELY REPORTED checks -- neither may be inferred from the
    generic per-field sweep above."""
    rep.line(
        "=== AC-11 MANDATORY: the two F4 escalations are EACH caught, named "
        "separately ==="
    )

    def _fn_hollowed() -> bool:
        trusted, _f_attested, f_hollowed, _f_escalated = _fixtures()
        try:
            resolve(f_hollowed, trusted)
        except ValueError:
            return True
        return False

    _try_check(
        rep,
        "F4(a): F-hollowed (consequential_sinks emptied after attestation, the "
        "disarming attack) makes resolve(agent, trusted) raise ValueError",
        _fn_hollowed,
    )

    def _fn_escalated() -> bool:
        trusted, _f_attested, _f_hollowed, f_escalated = _fixtures()
        try:
            resolve(f_escalated, trusted)
        except ValueError:
            return True
        return False

    _try_check(
        rep,
        "F4(b): F-escalated (trust_ceiling raised after attestation) makes "
        "resolve(agent, trusted) raise ValueError",
        _fn_escalated,
    )
    rep.line()


def run_ac15_refusal_raises_with_reason(rep: Report) -> None:
    """AC-15 (REQ-12). Refusal RAISES and carries a reason; no degraded context is
    ever returned. Checked for BOTH F-hollowed and F-escalated."""
    rep.line(
        "=== AC-15 (REQ-12): refusal RAISES, carries a reason, and returns no "
        "degraded context ==="
    )

    def _fn(which: str):
        def _inner() -> bool:
            trusted, _f_attested, f_hollowed, f_escalated = _fixtures()
            agent = f_hollowed if which == "hollowed" else f_escalated
            try:
                resolve(agent, trusted)
            except ValueError as exc:
                return bool(str(exc))
            # No exception raised: the refusal did NOT raise, which is itself the
            # failure this check exists to catch (a degraded context was returned
            # instead of a raise).
            return False
        return _inner

    _try_check(
        rep,
        "resolve(F-hollowed, trusted) raises ValueError carrying a non-empty reason "
        "(never returns a degraded context)",
        _fn("hollowed"),
    )
    _try_check(
        rep,
        "resolve(F-escalated, trusted) raises ValueError carrying a non-empty "
        "reason (never returns a degraded context)",
        _fn("escalated"),
    )

    def _fn_docstring() -> bool:
        doc = resolve.__doc__ or ""
        low = doc.lower()
        return ("not uniform" in low or "disarm" in low) and "consequential_sinks" in low

    _try_check(
        rep,
        "resolve()'s docstring states the fail-direction asymmetry: clamping "
        "narrows, but emptying consequential_sinks disarms, so a refusal raises "
        "rather than degrading",
        _fn_docstring,
    )
    rep.line()


def run_ac16_mandatory_no_friction(rep: Report) -> None:
    """AC-16. MANDATORY CONTROL. An honest, non-escalating attested binding must
    pass through resolve(agent, trusted) UNTOUCHED, with authoriser and attestation
    intact, and must produce classification results IDENTICAL to the same run with
    trusted=None. This is the anti-friction control every restriction in this build
    must be checked alongside."""
    rep.line("=== AC-16 MANDATORY CONTROL: an honest attested binding is not friction ===")

    def _fn_passthrough() -> bool:
        trusted, f_attested, _f_hollowed, _f_escalated = _fixtures()
        resolved = resolve(f_attested, trusted)
        return (
            resolved == f_attested
            and resolved.authoriser == f_attested.authoriser
            and resolved.attestation == f_attested.attestation
            and resolved.trust_ceiling == f_attested.trust_ceiling
            and resolved.consequential_sinks == f_attested.consequential_sinks
        )

    _try_check(
        rep,
        "resolve(F-attested, trusted) returns the input untouched, with authoriser "
        "and attestation INTACT and no clamp",
        _fn_passthrough,
    )

    def _fn_run_labels_identical() -> bool:
        from ontology.yggdrasil import load

        trusted, f_attested, _f_hollowed, _f_escalated = _fixtures()
        marshalled = MarshalledAssertion(
            "ac16.value", "taint:EXTERNAL_COMMS",
            {
                "subject_extracted": "transfer",
                "requested_action_summary": "wire transfer the funds to the supplier account",
            },
            flows=(MONEY_SINK,),
        )
        onto = load()
        with_trusted = Nornir(onto).run([marshalled], agent=f_attested, trusted=trusted)
        without_trusted = Nornir(onto).run([marshalled], agent=f_attested)
        a = with_trusted.by_id("ac16.value")
        b = without_trusted.by_id("ac16.value")
        return (
            a.type_name == b.type_name
            and a.trust_level == b.trust_level
            and a.action_critical == b.action_critical
            and a.consequential_sinks_at_classify == b.consequential_sinks_at_classify
        )

    _try_check(
        rep,
        "Nornir.run(assertions, F-attested, trusted) and Nornir.run(assertions, "
        "F-attested) (no trusted set) produce IDENTICAL type_name, trust_level, "
        "action_critical and consequential_sinks_at_classify -- attestation "
        "changes NO label",
        _fn_run_labels_identical,
    )

    def _fn_ec6_self_narrowing_not_friction() -> bool:
        """EC-6, the second mandatory anti-friction control: an honestly attested
        context whose ceiling is BELOW the global default's (a legitimately
        self-narrowing agent) must verify, pass through UNTOUCHED and NOT be
        clamped."""
        from ontology.nornir.authorisation_record import compute_record_attestation

        trusted, _f_attested, _f_hollowed, _f_escalated = _fixtures()
        base = AgentContext(
            agent_id="narrow-agent",
            permitted_actions=frozenset({"action:classify"}),
            trust_ceiling="TAINTED",  # at, not above, the global default's ceiling
            consequential_sinks=frozenset(),
        )
        digest = compute_record_attestation(base, PLATFORM_SECRET)
        narrow = AgentContext(
            agent_id=base.agent_id,
            permitted_actions=base.permitted_actions,
            trust_ceiling=base.trust_ceiling,
            consequential_sinks=base.consequential_sinks,
            authoriser=TRUSTED_AUTHORISER_ID,
            attestation=digest,
        )
        resolved = resolve(narrow, trusted)
        return (
            resolved == narrow
            and resolved.authoriser == TRUSTED_AUTHORISER_ID
            and resolved.attestation == digest
        )

    _try_check(
        rep,
        "EC-6, the second MANDATORY anti-friction control: a legitimately "
        "self-narrowing agent (ceiling AT the global default's, not above) "
        "verifies and passes through UNCLAMPED with its attested pair intact -- "
        "attestation must never be friction on a legitimately-scoped agent",
        _fn_ec6_self_narrowing_not_friction,
    )
    rep.line()


def run_ac17_ac18_clamp_clears_attestation(rep: Report) -> None:
    """AC-17, AC-18 (REQ-13). Verification does not suppress the D97 clamp: an
    HONESTLY attested but escalating context still gets clamped, and the clamped
    return carries NO attested pair (a derived context, not an attested one), so a
    re-verification of it refuses on the ACCURATE (unattested) path, not the
    misleading tampered path."""
    rep.line(
        "=== AC-17, AC-18 (REQ-13): the clamp still fires, and clears the attested "
        "pair ==="
    )

    def _build_honestly_escalated():
        from ontology.nornir.authorisation_record import compute_record_attestation

        base = AgentContext(
            agent_id="treasury",
            permitted_actions=frozenset({"action:classify"}),
            trust_ceiling="CANONICAL",
            consequential_sinks=frozenset({MONEY_SINK}),
        )
        digest = compute_record_attestation(base, PLATFORM_SECRET)
        return AgentContext(
            agent_id=base.agent_id,
            permitted_actions=base.permitted_actions,
            trust_ceiling=base.trust_ceiling,
            consequential_sinks=base.consequential_sinks,
            authoriser=TRUSTED_AUTHORISER_ID,
            attestation=digest,
        )

    def _fn_ac17() -> bool:
        trusted, _f_attested, _f_hollowed, _f_escalated = _fixtures()
        # An HONESTLY attested escalation: attest a context AT "CANONICAL" for
        # real, so the digest verifies cleanly, distinct from F-escalated (whose
        # digest is stale over the ORIGINAL "TAINTED" ceiling).
        honestly_escalated = _build_honestly_escalated()
        clamped = resolve(honestly_escalated, trusted)
        return (
            clamped.trust_ceiling == GLOBAL_DEFAULT.trust_ceiling
            and clamped.authoriser is None
            and clamped.attestation is None
        )

    _try_check(
        rep,
        "an HONESTLY attested but escalating context (digest verifies cleanly) "
        "still gets clamped by D97, and the clamped return carries "
        "authoriser=None, attestation=None",
        _fn_ac17,
    )

    def _fn_ac18() -> bool:
        trusted, _f_attested, _f_hollowed, _f_escalated = _fixtures()
        from ontology.nornir.authorisation_record import verify_record_attestation

        honestly_escalated = _build_honestly_escalated()
        clamped = resolve(honestly_escalated, trusted)
        res = verify_record_attestation(clamped, trusted)
        reason = res.reason.lower()
        return (
            not res.verified
            and ("unattested" in reason or "no verifiable" in reason or "absent" in reason)
            and "tamper" not in reason
            and "altered" not in reason
        )

    _try_check(
        rep,
        "re-verifying the clamped context REFUSES on the ACCURATE path -- named "
        "unattested, never tampered or altered (a legitimate clamp must not read "
        "as a detected tamper in the audit trail)",
        _fn_ac18,
    )
    rep.line()


def run_ac19_global_default_trust_root(rep: Report) -> None:
    """AC-19 (REQ-14). resolve(None, trusted) returns GLOBAL_DEFAULT by object
    identity, raises nothing, performs no verification, and GLOBAL_DEFAULT carries
    no authoriser or digest; resolve()'s docstring names it a trust root."""
    rep.line(
        "=== AC-19 (REQ-14): the global default is not refused, and is named a "
        "trust root ==="
    )

    def _fn() -> bool:
        trusted, _f_attested, _f_hollowed, _f_escalated = _fixtures()
        result = resolve(None, trusted)
        return (
            result is GLOBAL_DEFAULT
            and GLOBAL_DEFAULT.authoriser is None
            and GLOBAL_DEFAULT.attestation is None
        )

    _try_check(
        rep,
        "resolve(None, trusted) returns GLOBAL_DEFAULT by object identity, raises "
        "nothing, and GLOBAL_DEFAULT carries no authoriser or digest",
        _fn,
    )

    def _fn_docstring() -> bool:
        doc = resolve.__doc__ or ""
        return "trust root" in doc.lower()

    _try_check(
        rep,
        "resolve()'s docstring names GLOBAL_DEFAULT as a NAMED TRUST ROOT",
        _fn_docstring,
    )
    rep.line()


def run_ac20_both_import_orders(rep: Report) -> None:
    """AC-20 (REQ-16). Both import orders must succeed in a FRESH interpreter, via
    subprocess (this file lives under ontology/tests/, outside the invariant 3.1
    guard's scan scope, so a subprocess call here is not itself on the
    authorisation path). Also asserts control_surface.py contains NO module-level
    import of authorisation_record: only a function-local, relative import is
    permitted (REQ-16), on SinkRegistry.declare_attested's own precedent."""
    rep.line("=== AC-20 (REQ-16): both import orders succeed in a fresh interpreter ===")

    orders = [
        ("control_surface, THEN nornir",
         "import ontology.yggdrasil.control_surface, ontology.nornir"),
        ("nornir, THEN control_surface",
         "import ontology.nornir, ontology.yggdrasil.control_surface"),
    ]
    for label, code in orders:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
        )
        ok = proc.returncode == 0
        detail = "" if ok else f" [stderr: {proc.stderr.strip()[-400:]!r}]"
        rep.check(ok, f"fresh interpreter, import order ({label}): exits zero{detail}")

    def _fn_no_module_level_import() -> bool:
        from ontology.yggdrasil import control_surface as _cs

        source = inspect.getsource(_cs)
        tree = ast.parse(source)
        for node in tree.body:  # MODULE-LEVEL statements only
            if isinstance(node, ast.ImportFrom) and node.module and "authorisation_record" in node.module:
                return False
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "authorisation_record" in alias.name:
                        return False
        return True

    _try_check(
        rep,
        "control_surface.py contains NO module-level import of "
        "authorisation_record (function-local, relative imports only, on "
        "SinkRegistry.declare_attested's own precedent)",
        _fn_no_module_level_import,
    )
    rep.line()


def run_ac12_record_type_matches_constant(rep: Report) -> None:
    """AC-12 (REQ-9). record_type() equals the substrate's constant, by identity of
    value, so a future rename of the constant cannot leave a stale literal behind in
    control_surface.py."""
    rep.line(
        "=== AC-12 (REQ-9): record_type() is the constant, not a duplicated "
        "literal ==="
    )

    def _fn() -> bool:
        from ontology.nornir.authorisation_record import RECORD_TYPE_AGENT_CONTEXT

        agent = AgentContext(agent_id="x")
        return agent.record_type() == RECORD_TYPE_AGENT_CONTEXT

    _try_check(
        rep,
        "AgentContext('x').record_type() == "
        "authorisation_record.RECORD_TYPE_AGENT_CONTEXT",
        _fn,
    )
    rep.line()


def run_req18_invocation_boundary_detector(rep: Report) -> None:
    """REQ-18, AC-22. The opt-in residual must be mechanised, not left in prose: a
    live, AST-based detector, reusing gjoll_invocation_harness.py's OWN helpers
    (repository walk, call-target resolution, test-path classification), rather
    than a second detector mechanism, must determine how many call sites OUTSIDE
    ontology/tests/ call resolve() or Nornir.run with a trusted set supplied,
    resolved through the actual import. Fatal only if such a site appears outside
    an allowlist that is EMPTY today. Honesty note: the `Nornir.run` half of this
    detector is a best-effort heuristic (a bound `.run(...)` call in a file that
    imports `Nornir`, supplying a third positional argument or a `trusted=`
    keyword), because `Nornir.run` is a METHOD call on an arbitrary local instance
    name, unlike `gjoll.evaluate`'s free-function/qualified-module form that
    `gjoll_invocation_harness.py`'s alias tracking resolves precisely; that
    asymmetry is named here rather than hidden."""
    rep.line("=== REQ-18, AC-22: the opt-in trusted= boundary, detected live ===")

    from ontology.tests.gjoll_invocation_harness import (
        _iter_repo_python_files,
        _call_target,
        _is_test_path,
    )

    def _resolve_bound_names(tree: ast.Module) -> dict:
        bound: dict = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.ImportFrom) and node.module
                    and node.module.split(".")[-1] == "control_surface"):
                for alias in node.names:
                    if alias.name == "resolve":
                        bound[alias.asname or alias.name] = alias.name
        return bound

    def _control_surface_module_aliases(tree: ast.Module) -> set:
        aliases: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == "control_surface":
                        aliases.add(alias.asname or alias.name)
        return aliases

    def _imports_nornir_class(tree: ast.Module) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(a.name == "Nornir" for a in node.names):
                    return True
        return False

    def _supplies_trusted(node: ast.Call, min_positional: int) -> bool:
        """True if this call SUPPLIES a trusted set (a second positional argument
        for resolve, a third for Nornir.run, or a trusted= keyword) -- i.e.
        actually OPTS IN, not merely calls the function at all. A bare
        resolve(agent) or Nornir.run(assertions, agent) must NOT count: REQ-18
        counts sites that opt in, not every call site."""
        if len(node.args) >= min_positional:
            return True
        return any(kw.arg == "trusted" for kw in node.keywords)

    def _scan_module_for_trusted_opt_in(path: Path) -> list:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            return []
        hits: list = []
        resolve_bound = _resolve_bound_names(tree)
        cs_aliases = _control_surface_module_aliases(tree)
        has_nornir_import = _imports_nornir_class(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _call_target(node.func)
            if not target:
                # `.run(...)` on an arbitrary object -- the Nornir.run heuristic
                # (best-effort: this file imports Nornir AND the call is named
                # `run` AND supplies a 3rd positional arg or `trusted=`).
                if (isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                        and has_nornir_import
                        and _supplies_trusted(node, min_positional=3)):
                    hits.append(node.lineno)
                continue
            if target in resolve_bound and _supplies_trusted(node, min_positional=2):
                hits.append(node.lineno)
                continue
            obj, sep, attr = target.rpartition(".")
            if sep and obj in cs_aliases and attr == "resolve" and _supplies_trusted(
                node, min_positional=2
            ):
                hits.append(node.lineno)
        return sorted(hits)

    def _fn() -> bool:
        repo_root = _repo_root()
        non_test_hits: list = []
        test_hits: list = []
        for f in _iter_repo_python_files(repo_root):
            hits = _scan_module_for_trusted_opt_in(f)
            if not hits:
                continue
            rel = str(f.relative_to(repo_root))
            if _is_test_path(rel):
                test_hits.append(rel)
            else:
                non_test_hits.append(rel)
        rep.line(
            f"  [DETECTED] {len(test_hits)} test call site(s) supplying "
            f"trusted=/a second resolve() argument, {len(non_test_hits)} non-test "
            f"call site(s)"
        )
        for f in sorted(non_test_hits):
            rep.line(f"    [CRITICAL] unallowlisted non-test call site: {f}")
        return len(non_test_hits) == 0

    _try_check(
        rep,
        "zero non-test call sites supply a trusted set today (REQ-18's allowlist "
        "is empty and not yet violated); this obligation is fatal the moment a "
        "non-test site appears outside a reviewed allowlist entry",
        _fn,
    )

    def _fn_control_catches_planted_site() -> bool:
        """Negative control (invariant 3.10, D10): the detector must CATCH a
        planted call site supplying a trusted set, and must NOT flag an ordinary
        resolve(agent) call with none."""
        import tempfile

        d = Path(tempfile.mkdtemp())
        planted = d / "probe_planted.py"
        planted.write_text(
            "from ontology.yggdrasil.control_surface import resolve\n"
            "resolve(agent, my_trusted_set)\n"
        )
        clean = d / "probe_clean.py"
        clean.write_text(
            "from ontology.yggdrasil.control_surface import resolve\n"
            "resolve(agent)\n"
        )
        return (
            bool(_scan_module_for_trusted_opt_in(planted))
            and not _scan_module_for_trusted_opt_in(clean)
        )

    _try_check(
        rep,
        "the detector's own negative control: it CATCHES a planted call site "
        "supplying a trusted set, and does NOT flag an ordinary resolve(agent) "
        "call with none",
        _fn_control_catches_planted_site,
    )
    rep.line()


def run_ac23_residual_opt_in_survives(rep: Report) -> None:
    """AC-23 (REQ-30 limit 1). MANDATORY LIMIT. Enforcement is opt-in: with NO
    trusted set, F-hollowed is returned unchanged and nothing is detected. Reported
    as [RESIDUAL, RECORDED], pointing at REQ-18's detector as the mechanised owner
    of the fact, with an anti-drift [NOTE] retained so a future change making
    verification mandatory reports itself rather than passing silently."""
    rep.line("=== AC-23 (REQ-30 limit 1): the opt-in residual, asserted not hidden ===")

    survives = None
    try:
        hollowed = _build_hollowed_plain()
        result = resolve(hollowed)  # NO trusted set
        survives = result is hollowed and result.consequential_sinks == frozenset()
    except Exception as exc:  # pragma: no cover - reported, not swallowed
        rep.line(
            f"  [CRITICAL] could not even evaluate the opt-in-residual "
            f"reproduction: {type(exc).__name__}: {exc}"
        )

    if survives:
        rep.line(
            "  [RESIDUAL, RECORDED] enforcement is OPT-IN: resolve(agent) with NO "
            "trusted set returns a hollowed context unchanged and detects nothing "
            "(fail-open-by-omission). REQ-18's live detector above is the "
            "mechanised owner of the fact that no non-test caller opts in today; "
            "this line only restates it at resolve()'s own boundary so it cannot "
            "drift silently out of this suite's report either."
        )
    elif survives is False:
        rep.line(
            "  [NOTE] the opt-in residual no longer reproduces (resolve(agent) "
            "with NO trusted set no longer returns a hollowed context unchanged); "
            "if this was deliberate, update D103's decision text and REQ-11's "
            "byte-identical guarantee -- do not let this drift silently."
        )
    else:
        rep.line(
            "  [NOTE] the opt-in-residual reproduction could not be evaluated at "
            "all (see the CRITICAL line above); that is itself worth "
            "investigating, not absorbing."
        )
    rep.line()


def run_ac24_residual_trusted_lie_disarms(rep: Report) -> None:
    """AC-24 (REQ-30 limit 2). MANDATORY LIMIT, the sharpest one. A TRUSTED
    authoriser's LIE (an honestly attested, empty consequential_sinks set for a
    genuinely read-only agent) still verifies, and disarms the surface at a real
    money sink with NO sink_registry; the same proposal WITH the honest money-sink
    SinkRegistry supplied is BLOCKED. D94's obligation five, reproduced for the
    agent binding: attestation binds identity and integrity, never honesty."""
    rep.line(
        "=== AC-24 (REQ-30 limit 2), the sharpest one: a TRUSTED authoriser's LIE "
        "verifies and disarms the surface ==="
    )

    def _build_honest_lie():
        from ontology.nornir.authorisation_record import compute_record_attestation

        trusted = _build_f_trusted()
        base = AgentContext(
            agent_id="treasury",
            permitted_actions=frozenset({"action:classify"}),
            trust_ceiling="TAINTED",
            consequential_sinks=frozenset(),  # the lie: genuinely empty, honestly attested
        )
        digest = compute_record_attestation(base, PLATFORM_SECRET)
        lie = AgentContext(
            agent_id=base.agent_id,
            permitted_actions=base.permitted_actions,
            trust_ceiling=base.trust_ceiling,
            consequential_sinks=base.consequential_sinks,
            authoriser=TRUSTED_AUTHORISER_ID,
            attestation=digest,
        )
        return trusted, lie

    outcome = {"verifies": None, "authorised_no_registry": None, "blocked_with_registry": None}

    def _fn_verifies() -> bool:
        from ontology.nornir.authorisation_record import verify_record_attestation

        trusted, lie = _build_honest_lie()
        res = verify_record_attestation(lie, trusted)
        outcome["verifies"] = res.verified
        return res.verified

    _try_check(
        rep,
        "the honestly attested, genuinely empty consequential_sinks set VERIFIES "
        "(attestation proves WHO said it and that it is UNALTERED, never that it "
        "is TRUE)",
        _fn_verifies,
    )

    def _fn_no_registry_authorises() -> bool:
        trusted, lie = _build_honest_lie()
        resolved = resolve(lie, trusted)
        decision = _run_gate_no_registry(resolved)
        outcome["authorised_no_registry"] = decision.authorised
        return decision.authorised

    _try_check(
        rep,
        "the SAME proposal, gated at a real money sink with NO sink_registry, is "
        "AUTHORISED: a valid attestation of a disarmed control surface",
        _fn_no_registry_authorises,
    )

    def _fn_with_registry_blocks() -> bool:
        from ontology.yggdrasil import load

        trusted, lie = _build_honest_lie()
        resolved = resolve(lie, trusted)
        marshalled = MarshalledAssertion(
            "money.value.ac24", "taint:EXTERNAL_COMMS",
            {
                "subject_extracted": "transfer",
                "requested_action_summary": "wire transfer the funds to the supplier account",
            },
            flows=(MONEY_SINK,),
        )
        result = Nornir(load()).run([marshalled], agent=resolved)
        c = result.by_id("money.value.ac24")
        proposal = ActionProposal(
            "ac24-registry", MONEY_SINK, {c.assertion_id: CONSUME_ACTION}, declared_safe=False,
        )
        registry = SinkRegistry()
        registry.declare(
            SinkDeclaration(
                name=MONEY_SINK, parameters=frozenset({c.assertion_id}),
                consequential_by_default=True, effect_primitive=MOVE_MONEY,
            )
        )
        decision = evaluate(
            proposal, {c.assertion_id: c}, resolved.consequential_sinks,
            sink_registry=registry,
        )
        outcome["blocked_with_registry"] = not decision.authorised
        return not decision.authorised

    _try_check(
        rep,
        "the SAME proposal, WITH the honest money-sink SinkRegistry supplied, is "
        "BLOCKED -- the ONLY backstop the control surface has (D89-B), named "
        "explicitly rather than left implicit",
        _fn_with_registry_blocks,
    )

    if outcome["verifies"] and outcome["authorised_no_registry"] and outcome["blocked_with_registry"]:
        rep.line(
            "  [RESIDUAL, RECORDED] attestation binds IDENTITY and INTEGRITY, "
            "NEVER HONESTY. A TRUSTED authoriser who attests a HOLLOW "
            "consequential_sinks set produces a perfectly valid attestation of a "
            "disarmed control surface, and on the control surface there is NO "
            "ANALOGUE of D89-B or D93-D as an honesty backstop for the AGENT "
            "BINDING itself; the only backstop available is supplying a "
            "sink_registry at the GATE, which is a property of the SINK "
            "declaration, not of the agent's attested context. This is D94's "
            "identity-versus-honesty limit, reproduced here for the agent binding "
            "rather than the sink declaration."
        )
    elif outcome["verifies"] is False:
        rep.line(
            "  [NOTE] the honest lie no longer verifies (a genuinely empty, "
            "honestly attested consequential_sinks set is now REFUSED); if this "
            "was deliberate it would mean attestation now checks HONESTY, not "
            "merely identity and integrity -- update D103's decision text and "
            "this check's wording, do not let this drift silently."
        )
    else:
        rep.line(
            "  [NOTE] this residual reproduction did not complete as expected "
            "(see the checks above); that is itself worth investigating, not "
            "absorbing."
        )
    rep.line()


def run_ac25_residual_label_rewrite_untouched(rep: Report) -> None:
    """AC-25 (REQ-30 limit 3). MANDATORY LIMIT. D100's EC-8, the in-process label
    rewrite, is untouched and explicitly OUT of this build's threat model: a caller
    rewriting consequential_sinks_at_classify on a ClassifiedAssertion after
    resolve(agent, trusted) has verified, before the gate call, still disarms the
    no-registry branch."""
    rep.line(
        "=== AC-25 (REQ-30 limit 3): the in-process label rewrite (D100's EC-8) "
        "is untouched ==="
    )

    authorises = None
    try:
        from ontology.yggdrasil import load

        trusted, f_attested, _f_hollowed, _f_escalated = _fixtures()
        resolved = resolve(f_attested, trusted)  # verifies cleanly
        marshalled = MarshalledAssertion(
            "money.value.ac25", "taint:EXTERNAL_COMMS",
            {
                "subject_extracted": "transfer",
                "requested_action_summary": "wire transfer the funds to the supplier account",
            },
            flows=(MONEY_SINK,),
        )
        result = Nornir(load()).run([marshalled], agent=resolved, trusted=trusted)
        c = result.by_id("money.value.ac25")
        # The rewrite: a caller that already controls the process rewrites the
        # stamp AFTER the engine produced it, before the gate call.
        c.consequential_sinks_at_classify = frozenset()
        proposal = ActionProposal(
            "ac25-rewrite", MONEY_SINK, {c.assertion_id: CONSUME_ACTION}, declared_safe=False,
        )
        decision = evaluate(proposal, {c.assertion_id: c}, resolved.consequential_sinks)
        authorises = decision.authorised
    except Exception as exc:  # pragma: no cover - reported, not swallowed
        rep.line(
            f"  [CRITICAL] could not even evaluate the label-rewrite residual "
            f"reproduction: {type(exc).__name__}: {exc}"
        )

    if authorises:
        rep.line(
            "  [RESIDUAL, RECORDED] a caller that rewrites "
            "consequential_sinks_at_classify on a ClassifiedAssertion IN PROCESS, "
            "after resolve(agent, trusted) has verified and BEFORE the gate call, "
            "still disarms the no-registry branch. This is D100's EC-8, "
            "EXPLICITLY OUT of this build's threat model: attesting the binding "
            "binds the set at its ORIGIN; it does not stop a caller that already "
            "controls the process from rewriting a label downstream, exactly as "
            "it already could not stop a rewrite of action_critical or "
            "trust_level."
        )
    elif authorises is False:
        rep.line(
            "  [NOTE] the in-process label-rewrite residual no longer reproduces "
            "(a forged, attested-empty stamp on an already action-critical value "
            "is now blocked too); if this was deliberate, update D100's decision "
            "text and this check's wording -- do not let this drift silently."
        )
    else:
        rep.line(
            "  [NOTE] the label-rewrite residual reproduction could not be "
            "evaluated at all (see the CRITICAL line above); that is itself "
            "worth investigating, not absorbing."
        )
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("D103: AgentContext's integrity is enforced at resolve() (REQ-23, REQ-24)")
    rep.line("Extends D94's authoriser-plus-keyed-digest pattern, via the shared substrate")
    rep.line("(ontology.nornir.authorisation_record), to the agent binding itself: which")
    rep.line("actions an agent may perform, its trust ceiling, and -- most consequentially --")
    rep.line("which sinks count as consequential for it.")
    rep.line("")

    run_ac14_gap_reproduction(rep)
    run_altered_field_refused(rep)
    run_ec5_authoriser_is_covered(rep)
    run_unknown_authoriser_refused(rep)
    run_unattested_refused_three_shapes(rep)
    run_f4_escalations_mandatory(rep)
    run_ac15_refusal_raises_with_reason(rep)
    run_ac16_mandatory_no_friction(rep)
    run_ac17_ac18_clamp_clears_attestation(rep)
    run_ac19_global_default_trust_root(rep)
    run_ac20_both_import_orders(rep)
    run_ac12_record_type_matches_constant(rep)
    run_req18_invocation_boundary_detector(rep)
    run_ac23_residual_opt_in_survives(rep)
    run_ac24_residual_trusted_lie_disarms(rep)
    run_ac25_residual_label_rewrite_untouched(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: AgentContext's agent binding is attested (D103): an unattested,")
    print("unknown-authoriser or altered-after-attestation context is REFUSED at resolve()")
    print("where a trusted set is supplied, catching both F4 escalations (a raised ceiling, a")
    print("hollowed consequential-sink set); an honest binding passes through with no friction;")
    print("the D97 clamp still fires on an honest escalation and clears the attested pair; the")
    print("global default is a named trust root; both import orders hold; and the three")
    print("inherited limits (opt-in enforcement, identity-not-honesty, the untouched in-process")
    print("label rewrite) are reported, not hidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
