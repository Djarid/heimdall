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
    r.declare(SinkDeclaration(
        name="sink:payments.execute",
        parameters=frozenset({"amount", "destination"}),
        consequential_by_default=True,
    ))
    r.declare(SinkDeclaration(
        name="sink:log.write",
        parameters=frozenset({"message"}),
        consequential_by_default=False,
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


def test_agent_scoping_preserved(rep: Report) -> None:
    """D24 agent scoping must survive: a DECLARED sink that is not consequential for this agent
    is still legitimately ungated, with no error and no friction. The fix must distinguish
    'declared and out of scope' from 'not declared at all'."""
    rep.line("=== 6. Agent scoping (D24) is preserved for DECLARED sinks ===")
    reg = build_registry()
    agent_sinks = frozenset({"sink:payments.execute"})

    res = validate_proposal("sink:log.write", {"message": CONSUME_ACTION}, reg, KNOWN)
    rep.check(res.valid,
              "a declared, out-of-scope sink is NOT a validation error (no false friction)")
    rep.check(effective_consequential("sink:log.write", reg, agent_sinks) is False,
              "and it is correctly not consequential for this agent, so it stays ungated")
    rep.check(effective_consequential("sink:payments.execute", reg, agent_sinks) is True,
              "while the in-scope consequential sink is still gated as before")
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
    test_agent_scoping_preserved(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: an undeclared or mistyped sink, a silently-omitted parameter, an invalid")
    print("consume mode and a phantom parameter id are all caught and fail closed, while a")
    print("correct declaration passes and D24 agent scoping is preserved for declared sinks.")
    print("HONEST SCOPE: this does not attest that a declaration is HONEST. An author who")
    print("declares a consequential sink as non-consequential, or an action parameter as inert,")
    print("still defeats the gate; that is the open root seam (ADVERSARIAL_REVIEW 5.1) which")
    print("only attestation or derivation from real data flow can close. What is closed here is")
    print("the avoidable class where an ERROR or DRIFT silently disabled the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
