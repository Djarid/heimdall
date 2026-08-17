"""Test harness for promotion corroboration and graded review priority (mitigations 4 and 5).

Run from the repo root:

    python -m ontology.tests.promotion_policy_harness

Both mitigations act at the PROMOTION and REVIEW boundaries rather than at classification, so
neither depends on the classifier being right, which is the point: they hold even at the D77
false-inert rate. Tested by failure mode, with the mandatory controls that a non-consequential
fact keeps its single-source path (no new friction) and that a genuinely inert value with no
consequential involvement is still not queued at all.
"""

from __future__ import annotations

from ..nornir.promotion_policy import (
    ReviewPriority,
    SourcedValue,
    evaluate_promotion,
    review_priority,
)
from ..nornir.state_delta import SlotRef


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


BANK = SlotRef("supplier:acme", "bank_details")
COFFEE = SlotRef("office:kitchen", "coffee_machine_service_date")
EVIL = "GB99 EVIL 9999 9999"


def test_single_source_cannot_promote_consequential(rep: Report) -> None:
    """The BEC case: one channel asserting a new bank account must not become a trusted fact."""
    rep.line("=== 1. A consequential fact is not promotable on a single source ===")
    d = evaluate_promotion([SourcedValue(BANK, EVIL, "email:inbound")])
    rep.check(not d.promoted, "a single source cannot promote a consequential fact")
    rep.check(d.requires_human,
              "and it is routed to the human promotion gate rather than silently refused")
    rep.line()


def test_same_source_twice_is_not_corroboration(rep: Report) -> None:
    """An attacker who controls one channel must not manufacture corroboration by repeating."""
    rep.line("=== 2. The same source repeating itself is not corroboration ===")
    d = evaluate_promotion([
        SourcedValue(BANK, EVIL, "email:inbound"),
        SourcedValue(BANK, EVIL, "email:inbound"),
        SourcedValue(BANK, EVIL, "email:inbound"),
    ])
    rep.check(not d.promoted,
              "three assertions from ONE source do not satisfy the corroboration requirement")
    rep.check(d.requires_human, "and the request goes to the human gate")
    rep.line()


def test_independent_corroboration_promotes(rep: Report) -> None:
    """Two genuinely independent sources agreeing is the intended satisfying path."""
    rep.line("=== 3. Independent sources that agree do promote ===")
    d = evaluate_promotion([
        SourcedValue(BANK, EVIL, "email:inbound"),
        SourcedValue(BANK, EVIL, "portal:supplier-verified"),
    ])
    rep.check(d.promoted, "two distinct agreeing sources satisfy the requirement")
    rep.check(not d.requires_human, "and no human gate is needed")
    rep.line()


def test_human_approval_suffices(rep: Report) -> None:
    """The human is the corroboration of last resort; this is D76's gate in policy form."""
    rep.line("=== 4. Human approval satisfies the policy on its own ===")
    d = evaluate_promotion([SourcedValue(BANK, EVIL, "email:inbound")], human_approved=True)
    rep.check(d.promoted, "a single source plus human approval promotes")
    rep.line()


def test_conflict_never_promotes(rep: Report) -> None:
    """Disagreement is a stronger signal than either value: never resolve it by count."""
    rep.line("=== 5. Sources that disagree never promote, whatever the count ===")
    d = evaluate_promotion([
        SourcedValue(BANK, EVIL, "email:inbound"),
        SourcedValue(BANK, "GB11 SAFE 1111 1111", "portal:supplier-verified"),
        SourcedValue(BANK, EVIL, "feed:third"),
    ])
    rep.check(not d.promoted, "a conflict blocks promotion even with a majority")
    rep.check(d.conflict and d.requires_human, "and is flagged as a conflict for escalation")
    rep.line()


def test_non_consequential_keeps_single_source(rep: Report) -> None:
    """Mandatory control: this must not add friction to ordinary facts."""
    rep.line("=== 6. Control: a non-consequential fact still promotes on one source ===")
    d = evaluate_promotion([SourcedValue(COFFEE, "tuesday", "email:facilities")])
    rep.check(d.promoted, "a non-consequential slot promotes on a single source as before")
    rep.check(not d.requires_human, "with no human gate and no added friction")
    rep.line()


def test_graded_review_priority(rep: Report) -> None:
    """Mitigation 5: the middle row is the point. An inert-in-effect value that touches a
    consequential slot gets LOW review rather than none."""
    rep.line("=== 7. Graded review priority (the false-inert case gets SOME review) ===")
    rep.check(
        review_priority(effective_inert=True, touches_consequential_slot=True)
        is ReviewPriority.LOW,
        "inert in effect BUT touches a consequential slot: LOW review, not none "
        "(restores coverage the binary outcome lost)",
    )
    rep.check(
        review_priority(effective_inert=True, touches_consequential_slot=False)
        is ReviewPriority.NONE,
        "control: genuinely inert with no consequential involvement is not queued at all",
    )
    rep.check(
        review_priority(effective_inert=False, touches_consequential_slot=True,
                        has_structural_signal=True)
        is ReviewPriority.HIGH,
        "denied inertness on STRUCTURAL evidence: HIGH priority",
    )
    rep.check(
        review_priority(effective_inert=False, touches_consequential_slot=True,
                        has_structural_signal=False)
        is ReviewPriority.NORMAL,
        "denied inertness on weak content evidence only: NORMAL priority",
    )
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("Promotion corroboration and graded review priority: mitigations 4 and 5")
    rep.line("Both act at the promotion and review boundaries, so neither depends on the")
    rep.line("classifier being right; they hold even at the D77 false-inert rate.")
    rep.line("")

    test_single_source_cannot_promote_consequential(rep)
    test_same_source_twice_is_not_corroboration(rep)
    test_independent_corroboration_promotes(rep)
    test_human_approval_suffices(rep)
    test_conflict_never_promotes(rep)
    test_non_consequential_keeps_single_source(rep)
    test_graded_review_priority(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: a consequential fact cannot be promoted on one source's word, repeating")
    print("one source is not corroboration, conflicts escalate rather than resolve by count,")
    print("human approval suffices, ordinary facts keep their single-source path, and an")
    print("inert-in-effect value touching a consequential slot now gets LOW review rather than")
    print("none. HONEST SCOPE: corroboration presumes genuinely independent sources; two")
    print("channels an attacker controls are one source in effect, and judging independence is")
    print("a deployment question this policy expresses but does not settle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
