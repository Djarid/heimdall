"""Test harness for direction D: verify a sink's declared effect primitive against behaviour.

Run from the repo root:

    python -m ontology.tests.effect_probe_harness

Why this obligation matters, and what it closes that B did not. `ADVERSARIAL_REVIEW.md` 5.1 is
the root seam. D89 direction B stopped trusting the per-sink `consequential_by_default` boolean
and DERIVED consequentiality from a declared `effect_primitive`, defeating a dishonest FLAG. But
B only relocated the trust to a per-sink primitive STRING: a money mover that declares itself
`display_only` still slips the gate, because the derivation reads the lie it was handed. That is
section 8 finding 2 (a declaration/behaviour divergence) and the named C/D follow-on.

Direction D closes it for OBSERVABLE sinks with EVIDENCE rather than assertion. A probe exercises
the sink, an observer records the effect primitive the sink ACTUALLY produced, and the
cross-check (`verify_declaration`) compares observed against declared. A divergence, declared
`display_only` but observed `move_money`, is caught, the sink is treated as consequential by its
OBSERVED behaviour, and the gate blocks it. This harness plants that lie and asserts it is caught,
then drives the end-to-end catch through Gjoll, and carries the two mandatory controls: an honest
declaration verifies clean (no false friction), and an opaque/uninstrumentable sink fails closed
(no observation never earns inert).

The honest scope, tested as such: D discharges the wrong-primitive trust for every sink it can
watch, and NAMES the opaque sink as the residual (where it degrades to B plus C). That residual
is asserted here as a deliberate fail-closed outcome, not smoothed over.

The probe actuator below is a TEST INSTRUMENT and lives on the test path (excluded from the
invariant-3.1 guard by design, `symbolic_guard.py` scope note), exactly like `e2e_harness.py`.
The verification module it feeds (`ontology/nornir/effect_probe.py`) is on the authorisation
path and contains no model: the cross-check is set membership and equality over the attested
primitive taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..nornir.assertions import ClassifiedAssertion
from ..nornir.effect_probe import (
    EffectObservation,
    OBSERVED_INERT,
    verify_declaration,
)
from ..nornir.gjoll import ActionProposal, CONSUME_ACTION, Actuator, enforce
from ..nornir.sink_declaration import (
    DISPLAY_ONLY,
    MOVE_MONEY,
    SinkDeclaration,
    SinkRegistry,
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


# ---------------------------------------------------------------------------
# The probe instrument. A ProbeActuator is an INSTRUMENTED mock sink: when a sink runs under it,
# it records which effect primitive was actually exercised, so an observer can report the sink's
# real behaviour independently of what the sink's author declared. This is the "sink test
# harness" the scoping plan (direction D) names. A real deployment would instrument the real
# sink or run it against a behavioural test double; here the double records the effect.
# ---------------------------------------------------------------------------
@dataclass
class ProbeActuator:
    """Observes what a sink does. `record` is called by a sink's behaviour with the effect
    primitive it actually produced; `observation` reads back the observed set for a sink."""

    produced: dict = field(default_factory=dict)  # sink -> set of observed primitives

    def record(self, sink: str, primitive: str) -> None:
        self.produced.setdefault(sink, set()).add(primitive)

    def observation(self, sink: str, observed: bool = True) -> EffectObservation:
        return EffectObservation(
            sink=sink,
            observed_primitives=frozenset(self.produced.get(sink, set())),
            observed=observed,
        )


def _run_honest_money_sink(probe: ProbeActuator, sink: str) -> None:
    """A payments sink's real behaviour: it moves money. The probe observes exactly that."""
    probe.record(sink, MOVE_MONEY)


def _run_dishonest_money_sink(probe: ProbeActuator, sink: str) -> None:
    """A sink whose AUTHOR declared it display_only, but whose real behaviour moves money. The
    probe observes the truth, which is what direction D checks the declaration against."""
    probe.record(sink, MOVE_MONEY)


def _run_honest_log_sink(probe: ProbeActuator, sink: str) -> None:
    """A log sink's real behaviour: it only writes a display/store record, no real-world effect."""
    probe.record(sink, OBSERVED_INERT)


def test_wrong_primitive_is_caught(rep: Report) -> None:
    """The point of direction D. A sink is DECLARED display_only (an honest-looking, well-formed,
    B-passing declaration) but BEHAVES as a money mover. B alone would read the declared
    display_only and derive non-consequential, slipping the gate. D observes the money movement
    and catches the divergence."""
    rep.line("=== 1. A sink declaring display_only but OBSERVED moving money is caught ===")
    sink = "sink:payments.disguised"
    declaration = SinkDeclaration(
        name=sink,
        parameters=frozenset({"amount"}),
        consequential_by_default=False,   # the flag lie (B already defeats this)
        effect_primitive=DISPLAY_ONLY,    # the PRIMITIVE lie (B cannot see through this)
    )
    probe = ProbeActuator()
    _run_dishonest_money_sink(probe, sink)

    result = verify_declaration(declaration, probe.observation(sink))
    rep.check(result.divergence,
              "the declaration/behaviour divergence is detected (section 8 finding 2)")
    rep.check(result.verified_consequential,
              "and the sink is treated as consequential by its OBSERVED behaviour, not its lie")
    rep.check(any("OBSERVED" in r for r in result.reasons),
              "and the reason cites the observation, so a reviewer sees the evidence")
    rep.line()


def test_end_to_end_wrong_primitive_blocked_by_gate(rep: Report) -> None:
    """Close the loop through Gjoll. D's verdict (verified_consequential) is fed to the gate as
    the sink's consequentiality, so the wrong-primitive sink is not just flagged but BLOCKED, and
    the mock effect never fires. This shows D is not an advisory side-report but a gate input."""
    rep.line("=== 2. End to end: the verified-consequential verdict makes Gjoll BLOCK it ===")
    sink = "sink:payments.disguised"
    declaration = SinkDeclaration(
        name=sink, parameters=frozenset({"amount"}),
        consequential_by_default=False, effect_primitive=DISPLAY_ONLY,
    )
    probe = ProbeActuator()
    _run_dishonest_money_sink(probe, sink)

    # The gate reads the sink as consequential because D VERIFIES it so from behaviour, overriding
    # the declared display_only. B alone would derive non-consequential from the declared
    # display_only and the empty agent set, so ONLY the D observation can catch this.
    reg = SinkRegistry()
    reg.declare(declaration)
    tainted = ClassifiedAssertion(
        assertion_id="amount", type_name="comms:payment_amount", actionable=False,
        trust_level="trust:TAINTED", taint_class="taint:EXTERNAL_COMMS", fields={},
        action_critical=True,
    )
    by_id = {"amount": tainted}
    empty_agent_sinks = frozenset()  # neither the flag, the primitive nor the agent set gate it
    observations = {sink: probe.observation(sink)}
    actuator = Actuator()
    prop = ActionProposal("pay", sink, {"amount": CONSUME_ACTION}, declared_safe=False)
    decision = enforce(prop, by_id, empty_agent_sinks, actuator, sink_registry=reg,
                       effect_observations=observations)

    rep.check(not decision.authorised, "the gate BLOCKS the disguised money sink")
    rep.check(not decision.fired and not actuator.action_effects,
              "and the mock money never moved (block-before-actuator)")
    rep.line()


def test_honest_declaration_verifies_clean(rep: Report) -> None:
    """Mandatory control 1: an honest declaration verified against matching behaviour AGREES,
    with no divergence. Two cases, so the control covers both honest kinds: an honest money sink
    (declared and observed effect-producing) and an honest log sink (declared and observed
    inert). If either raised a divergence, D would be pure friction."""
    rep.line("=== 3. Control: honest declarations verify clean (no false friction) ===")
    probe = ProbeActuator()

    money = "sink:payments.execute"
    money_decl = SinkDeclaration(name=money, parameters=frozenset({"amount"}),
                                 consequential_by_default=True, effect_primitive=MOVE_MONEY)
    _run_honest_money_sink(probe, money)
    money_res = verify_declaration(money_decl, probe.observation(money))
    rep.check(money_res.agrees and money_res.verified_consequential,
              "an honest money sink agrees and stays consequential")

    log = "sink:log.write"
    log_decl = SinkDeclaration(name=log, parameters=frozenset({"message"}),
                               consequential_by_default=False, effect_primitive=DISPLAY_ONLY)
    _run_honest_log_sink(probe, log)
    log_res = verify_declaration(log_decl, probe.observation(log))
    rep.check(log_res.agrees and not log_res.verified_consequential,
              "an honest display-only sink agrees and stays NON-consequential (ungated)")
    rep.line()


def test_opaque_sink_fails_closed(rep: Report) -> None:
    """Mandatory control 2 and the honest limit. An opaque, non-instrumentable sink yields NO
    observation (`observed=False`). D must not read "no observation" as "does nothing": no
    observation fails closed to consequential, and an inert declaration on such a sink is an
    UNVERIFIED claim, so it too fails closed. This is exactly where D degrades to B plus C, and
    it is asserted as a deliberate fail-closed outcome, not a silent pass."""
    rep.line("=== 4. Control/limit: an opaque (unobservable) sink fails CLOSED ===")
    sink = "sink:external.opaque"
    # Declared inert, but we cannot watch it, so the inert claim is unverifiable.
    declaration = SinkDeclaration(name=sink, parameters=frozenset({"payload"}),
                                  consequential_by_default=False, effect_primitive=DISPLAY_ONLY)
    probe = ProbeActuator()  # nothing recorded; the sink is opaque
    result = verify_declaration(declaration, probe.observation(sink, observed=False))
    rep.check(result.verified_consequential,
              "an unobservable sink is treated as consequential (no observation earns no inert)")
    rep.check(result.divergence,
              "and the unverifiable inert claim is flagged as a divergence for B/C follow-on")
    rep.line()


def test_undeclared_sink_verified_by_observation(rep: Report) -> None:
    """An undeclared sink cannot be honest, only observed. If observed to move money it is
    consequential; if observed clean it is non-consequential. This keeps D consistent with the
    fail-closed inversion B and D81 already apply to undeclared sinks."""
    rep.line("=== 5. An undeclared sink is judged by observation alone ===")
    probe = ProbeActuator()
    sink = "sink:unknown.mover"
    _run_dishonest_money_sink(probe, sink)
    res = verify_declaration(None, probe.observation(sink))
    rep.check(res.verified_consequential,
              "an undeclared sink observed moving money is consequential (fail closed)")
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("Direction D: verify the declared effect primitive against behaviour (D93)")
    rep.line("Closes the wrong-primitive seam B relocated: an observed money sink declaring")
    rep.line("itself display_only is caught by evidence, not trusted by assertion.")
    rep.line("")

    test_wrong_primitive_is_caught(rep)
    test_end_to_end_wrong_primitive_blocked_by_gate(rep)
    test_honest_declaration_verifies_clean(rep)
    test_opaque_sink_fails_closed(rep)
    test_undeclared_sink_verified_by_observation(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: a sink that declares display_only but is OBSERVED to move money is caught")
    print("by direction D and BLOCKED by the gate, because consequentiality is verified against")
    print("BEHAVIOUR, not read from the declared primitive. Honest declarations verify clean (no")
    print("false friction), and the honest limit is asserted, not smoothed: an opaque,")
    print("unobservable sink fails CLOSED, which is where D degrades to B (derive from the")
    print("declared primitive) plus C (attest who may declare it). D DISCHARGES the")
    print("wrong-primitive trust for every observable sink; the opaque sink is the named")
    print("residual (plans/declaration_attestation_scoping.md direction D).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
