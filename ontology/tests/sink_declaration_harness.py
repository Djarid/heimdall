"""Test harness for the sink-declaration schema and its fail-closed validation (mitigation 3).

Run from the repo root:

    python -m ontology.tests.sink_declaration_harness

Why this obligation matters most. `ADVERSARIAL_REVIEW.md` 5.1 ranks sink and flow declarations
as the root seam, and D78 showed the false-inert containment rests on them, because the gate is
declaration-driven rather than classification-driven. Three fail-open paths existed, each
triggered by a declaration ERROR rather than an attack, and each silently authorising. Each
obligation below plants one of those errors and asserts it is now caught.

Tested by failure mode throughout, and with the mandatory control that a correct declaration
still passes (otherwise the validation would be pure friction) and that legitimate agent-scoped
non-consequential sinks are still ungated (otherwise D24 scoping would be broken).
"""

from __future__ import annotations

from ..nornir.sink_declaration import (
    CONSUME_ACTION,
    CONSUME_INERT,
    DISPLAY_ONLY,
    MOVE_MONEY,
    SinkDeclaration,
    SinkRegistry,
    effective_consequential,
    validate_proposal,
)


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


def build_registry() -> SinkRegistry:
    r = SinkRegistry()
    # Honest declarations under direction B: the effect primitive is the source of truth for
    # consequentiality. A payments sink moves money (effect-producing); a log sink is
    # display/store only (honestly inert). consequential_by_default is retained for the D81
    # tests and reporting but no longer decides consequentiality.
    r.declare(SinkDeclaration(
        name="sink:payments.execute",
        parameters=frozenset({"amount", "destination"}),
        consequential_by_default=True,
        effect_primitive=MOVE_MONEY,
    ))
    r.declare(SinkDeclaration(
        name="sink:log.write",
        parameters=frozenset({"message"}),
        consequential_by_default=False,
        effect_primitive=DISPLAY_ONLY,
    ))
    return r


KNOWN = frozenset({"amount", "destination", "message"})


def test_unknown_sink_fails_closed(rep: Report) -> None:
    """Fail-open path 1, the worst: a typo or rename made the sink unknown, which made
    `sink_is_consequential` False, which authorised everything."""
    rep.line("=== 1. An undeclared or mistyped sink fails CLOSED (was fail-open) ===")
    reg = build_registry()
    agent_sinks = frozenset({"sink:payments.execute"})

    # A realistic typo of the declared sink id.
    typo = "sink:payments.exceute"
    res = validate_proposal(typo, {"amount": CONSUME_ACTION}, reg, KNOWN)
    rep.check(not res.valid, "a mistyped sink id is a validation error, not a silent pass")
    rep.check(res.treat_as_consequential,
              "and it is treated as CONSEQUENTIAL, so the gate is not disabled by the typo")
    rep.check(effective_consequential(typo, reg, agent_sinks) is True,
              "effective_consequential returns True for an undeclared sink (fail closed)")
    rep.line()


def test_silent_omission_caught(rep: Report) -> None:
    """Fail-open path 2: a parameter the sink really uses, absent from `consumes`, was never
    checked at all."""
    rep.line("=== 2. A silently-omitted parameter is caught (was never gated) ===")
    reg = build_registry()
    # 'destination' is the dangerous one and is omitted entirely.
    res = validate_proposal(
        "sink:payments.execute", {"amount": CONSUME_ACTION}, reg, KNOWN
    )
    rep.check(not res.valid, "omitting a declared parameter is a validation error")
    rep.check(any("destination" in e for e in res.errors),
              "and the error names the unaccounted parameter")
    rep.line()


def test_invalid_mode_caught(rep: Report) -> None:
    """Fail-open path 3: a mode typo was skipped as if it meant inert consumption."""
    rep.line("=== 3. An invalid consume mode is caught (was read as inert) ===")
    reg = build_registry()
    for bad in ("action", "ACTIION", "", "Action"):
        res = validate_proposal(
            "sink:payments.execute",
            {"amount": bad, "destination": CONSUME_INERT},
            reg,
            KNOWN,
        )
        rep.check(not res.valid, f"mode {bad!r} is rejected rather than treated as inert")
    rep.line()


def test_phantom_parameter_caught(rep: Report) -> None:
    """Declaration drift: a parameter id that no longer corresponds to a real assertion."""
    rep.line("=== 4. A phantom parameter id is caught (declaration drift) ===")
    reg = build_registry()
    res = validate_proposal(
        "sink:payments.execute",
        {"amount": CONSUME_ACTION, "destination": CONSUME_ACTION, "ghost": CONSUME_ACTION},
        reg,
        KNOWN,
    )
    rep.check(not res.valid, "a parameter that is not a known classified assertion is an error")
    rep.check(any("ghost" in e for e in res.errors), "and the error names it")
    rep.line()


def test_correct_declaration_passes(rep: Report) -> None:
    """The mandatory control. If a correct declaration failed, this would be pure friction."""
    rep.line("=== 5. Control: a correct, complete declaration passes ===")
    reg = build_registry()
    res = validate_proposal(
        "sink:payments.execute",
        {"amount": CONSUME_ACTION, "destination": CONSUME_ACTION},
        reg,
        KNOWN,
    )
    rep.check(res.valid, "a complete, well-formed declaration validates cleanly")
    rep.check(not res.treat_as_consequential,
              "and does not trigger the fail-closed consequential override")
    rep.line()


def test_intrinsically_inert_sink_ungated(rep: Report) -> None:
    """No false friction: a sink that HONESTLY declares an inert effect primitive
    (display/store only) stays ungated, with no error. Under D89 (direction B) this is now the
    RIGHT reason a log sink is ungated: not because it is out of the agent's scope, but because
    its effect primitive is not effect-producing. The fix must not gate a genuinely inert
    sink (that would be pure friction), while still gating a real effect sink."""
    rep.line("=== 6. Control: an HONESTLY inert sink (display/store primitive) stays ungated ===")
    reg = build_registry()
    agent_sinks = frozenset({"sink:payments.execute"})

    res = validate_proposal("sink:log.write", {"message": CONSUME_ACTION}, reg, KNOWN)
    rep.check(res.valid,
              "a declared display-only sink is NOT a validation error (no false friction)")
    rep.check(effective_consequential("sink:log.write", reg, agent_sinks) is False,
              "and it is correctly non-consequential by its inert effect primitive, so ungated")
    rep.check(effective_consequential("sink:payments.execute", reg, agent_sinks) is True,
              "while the money-moving sink is consequential by its effect primitive")
    rep.line()


def test_dishonest_flag_still_gated(rep: Report) -> None:
    """D89, direction B, the point of the whole change: an author declares a genuinely
    consequential sink with consequential_by_default=False (a dishonest flag), and it is NOT in
    the agent's consequential set. Under D81 this defeated the gate (effective_consequential
    returned False). Under B, consequentiality is DERIVED from the effect primitive, so the
    money-moving sink stays consequential however the flag is set and whatever the agent set
    contains."""
    rep.line("=== 7. A dishonestly-flagged consequential sink is STILL gated (direction B) ===")
    reg = SinkRegistry()
    # The dishonest declaration: a money mover flagged non-consequential, and the empty agent
    # set, so nothing but the derivation can catch it.
    reg.declare(SinkDeclaration(
        name="sink:payments.execute",
        parameters=frozenset({"amount", "destination"}),
        consequential_by_default=False,          # the lie
        effect_primitive=MOVE_MONEY,             # the truth the derivation reads
    ))
    empty_agent_sinks = frozenset()

    res = validate_proposal(
        "sink:payments.execute",
        {"amount": CONSUME_ACTION, "destination": CONSUME_ACTION},
        reg, KNOWN,
    )
    rep.check(res.valid, "the dishonest declaration is well-FORMED, so D81 validation passes it")
    rep.check(effective_consequential("sink:payments.execute", reg, empty_agent_sinks) is True,
              "but B DERIVES consequentiality from the money-movement primitive, so it is gated "
              "despite the false flag and the empty agent set")
    rep.line()


def test_undeclared_primitive_fails_closed(rep: Report) -> None:
    """Silence never earns inert. A sink declared with NO effect primitive (effect_primitive is
    None) fails closed to consequential, the same inversion as an undeclared sink, so an author
    cannot dodge the derivation by simply omitting the primitive."""
    rep.line("=== 8. A sink with NO declared effect primitive fails closed to consequential ===")
    reg = SinkRegistry()
    reg.declare(SinkDeclaration(
        name="sink:mystery.op",
        parameters=frozenset({"payload"}),
        consequential_by_default=False,
        effect_primitive=None,                   # omitted entirely
    ))
    rep.check(effective_consequential("sink:mystery.op", reg, frozenset()) is True,
              "an omitted effect primitive is treated as consequential (silence fails closed)")
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("Sink-declaration schema and fail-closed validation: mitigation 3")
    rep.line("Closes the class where a declaration ERROR silently disabled the gate.")
    rep.line("")

    test_unknown_sink_fails_closed(rep)
    test_silent_omission_caught(rep)
    test_invalid_mode_caught(rep)
    test_phantom_parameter_caught(rep)
    test_correct_declaration_passes(rep)
    test_intrinsically_inert_sink_ungated(rep)
    test_dishonest_flag_still_gated(rep)
    test_undeclared_primitive_fails_closed(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: an undeclared or mistyped sink, a silently-omitted parameter, an invalid")
    print("consume mode and a phantom parameter id are all caught and fail closed (D81); a")
    print("correct declaration passes and an honestly-inert sink stays ungated (no friction);")
    print("and under D89 direction B a DISHONESTLY-flagged consequential sink is still gated,")
    print("because consequentiality is DERIVED from the sink's effect primitive over the")
    print("attested EFFECT_PRODUCING_PRIMITIVES table, not read from the per-sink boolean or the")
    print("agent set. Silence (no primitive) fails closed to consequential.")
    print("HONEST SCOPE, narrowed but not closed: B relocates the trust from a per-sink flag to")
    print("one small attested table, so a wrong-flag attack is defeated, but a sink that")
    print("dishonestly declares the WRONG primitive (a money sink claiming display_only) is")
    print("still defeated. Closing that needs C (attest who may declare) or D (verify the")
    print("primitive against behaviour), the named follow-ons in")
    print("plans/declaration_attestation_scoping.md. The A half (fail-closed consume mode) is")
    print("proven in the gate harness, not here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
