"""Test harness for two-dimensional classification (mitigation 2 for the D67 break).

Run from the repo root:

    python -m ontology.tests.consequence_axis_harness

What is being tested, and what is NOT. The claim under test is the removal of an OVERRIDE, not
the accuracy of any consequence detector. The single-label design lets an inert speech act
erase a co-present consequence signal; the two-dimensional design records consequence on an
axis the speech-act type cannot suppress, so effective inertness becomes a conjunction. These
obligations test that structural property, plus the composition with the state-delta detector
(D79), plus the mandatory control that a genuine informational statement with an empty axis is
still inert (otherwise the change would be pure friction).

The harness deliberately does NOT claim the content-derived subject signal fixes anything: it
is marked weak, and there is an obligation below showing the structural signal carries the case
when the content signal misses, which is the honest division of labour.
"""

from __future__ import annotations

from ..nornir.consequence_axis import (
    SignalStrength,
    classify_two_dimensional,
    flow_to_sink_signal,
    state_delta_signal,
    subject_match_signal,
)
from ..nornir.state_delta import (
    ProposedFact,
    SlotRef,
    dict_oracle,
    evaluate,
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


INERT_SPEECH_ACT = "comms:informational_statement"


def test_override_is_removed(rep: Report) -> None:
    """The core structural property: an inert speech act no longer suffices on its own."""
    rep.line("=== 1. The inert speech act can no longer suppress a consequence signal ===")

    # The D77 shape: a genuinely informational speech act about a payment.
    o = classify_two_dimensional(
        INERT_SPEECH_ACT, True, [subject_match_signal("subject is a standing order (payment)")]
    )
    rep.check(o.speech_act_is_inert, "the speech act is still typed inert (Nornir unchanged)")
    rep.check(not o.effective_inert,
              "but it is NOT inert IN EFFECT, because the consequence axis is occupied")
    rep.check(o.suppressed_consequence,
              "and the case is reported as one the old single-label design would have "
              "mis-typed inert (the rescue is visible, not silent)")
    rep.line()


def test_genuine_informational_still_inert(rep: Report) -> None:
    """The mandatory control. If this failed, the change would be pure friction."""
    rep.line("=== 2. Control: a genuine informational statement is still inert ===")
    o = classify_two_dimensional(INERT_SPEECH_ACT, True, [])
    rep.check(o.effective_inert,
              "inert speech act with an EMPTY consequence axis stays inert in effect")
    rep.check(not o.suppressed_consequence, "and is not reported as a rescued case")
    rep.check(o.disposition() == "inert", "disposition is 'inert'")
    rep.line()


def test_structural_signal_carries_when_content_misses(rep: Report) -> None:
    """The honest division of labour: the content signal is evadable, the structural one is
    not, and the structural one alone is enough to deny effective inertness."""
    rep.line("=== 3. A structural signal alone denies inertness (content signal absent) ===")

    # The fi-20/ind-20 metaphor shape: no content subject signal fires at all, because the
    # wording is a metaphor. The state delta still does.
    o = classify_two_dimensional(
        INERT_SPEECH_ACT, True,
        [state_delta_signal("changes employee:jh::salary_destination")],
    )
    rep.check(not o.effective_inert,
              "a metaphorically-phrased case with NO content signal is still denied inert, "
              "because the structural state-delta signal occupies the axis")
    rep.check(o.consequence.has_structural, "the signal is recorded as STRUCTURAL")
    rep.check("gate" in o.disposition(),
              "and it routes to the gate rather than merely to review, because the evidence "
              "is structural")
    rep.line()


def test_composition_with_state_delta(rep: Report) -> None:
    """End to end with the real D79 detector: a false-inert payroll redirect, expressed as a
    slot binding, is denied effective inertness by composing the two mitigations."""
    rep.line("=== 4. Composition with the real state-delta detector (D79) ===")
    baseline = {"employee:jh::salary_destination": "GB22 SAFE 2222 2222"}
    oracle = dict_oracle(baseline)
    verdict = evaluate(
        [ProposedFact(SlotRef("employee:jh", "salary_destination"), "GB99 EVIL 9999 9999")],
        oracle,
    )
    rep.check(verdict.deny_inert, "D79 flags the payroll redirect as a consequential delta")

    signals = [state_delta_signal(r) for r in verdict.reasons()]
    o = classify_two_dimensional(INERT_SPEECH_ACT, True, signals)
    rep.check(not o.effective_inert,
              "and the two-dimensional outcome denies effective inertness on that basis")
    rep.check(o.suppressed_consequence,
              "a case the single-label design would have typed inert is rescued end to end")
    rep.line()


def test_signal_strength_is_honest(rep: Report) -> None:
    """The audit trail must distinguish evadable from non-evadable evidence, so a reader can
    see whether inertness was denied on strong or weak grounds."""
    rep.line("=== 5. Signal strength is recorded honestly (evadable vs not) ===")
    content = subject_match_signal("mentions a payment")
    structural = state_delta_signal("changes a consequential slot")
    flow = flow_to_sink_signal("reaches sink:payments.execute")
    rep.check(content.strength is SignalStrength.CONTENT,
              "a content subject match is marked CONTENT (weak, evadable per 3.5)")
    rep.check(structural.strength is SignalStrength.STRUCTURAL,
              "a state delta is marked STRUCTURAL (not evadable by rephrasing)")
    rep.check(flow.strength is SignalStrength.STRUCTURAL,
              "a flow-to-sink reachability result is marked STRUCTURAL")

    weak_only = classify_two_dimensional(INERT_SPEECH_ACT, True, [content])
    rep.check("review" in weak_only.disposition(),
              "an inert speech act denied only by WEAK evidence routes to review, not the gate")
    rep.line()


def test_non_inert_speech_act_unaffected(rep: Report) -> None:
    """A high-risk speech act is untouched by this layer: the existing path still applies."""
    rep.line("=== 6. A non-inert speech act is unaffected (no behaviour change there) ===")
    o = classify_two_dimensional("comms:payment_request", False, [])
    rep.check(not o.effective_inert, "a high-risk type is not inert in effect")
    rep.check(not o.suppressed_consequence, "and is not a rescued case")
    rep.check("existing high-risk or review path applies" in o.disposition(),
              "disposition defers to the existing path")
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("Two-dimensional classification: mitigation 2 for the D67 false-inert break")
    rep.line("Speech act and consequence are separate axes; an inert type cannot suppress a")
    rep.line("consequence signal. The fix is the removal of the OVERRIDE, not detector accuracy.")
    rep.line("")

    test_override_is_removed(rep)
    test_genuine_informational_still_inert(rep)
    test_structural_signal_carries_when_content_misses(rep)
    test_composition_with_state_delta(rep)
    test_signal_strength_is_honest(rep)
    test_non_inert_speech_act_unaffected(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: the override is removed. An inert speech act no longer erases a")
    print("co-present consequence signal, structural signals carry cases the content signal")
    print("misses, and a genuine informational statement with an empty axis is still inert.")
    print("HONEST SCOPE: the content-derived subject signal remains evadable (3.5) and is")
    print("marked weak; the structural signals (state delta, flow-to-sink) are what carry the")
    print("guarantee. This fixes the collapse, it does not make consequence detection perfect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
