"""Test harness for state-delta consequence detection (mitigation 1 for the D67 break).

Run from the repo root:

    python -m ontology.tests.state_delta_harness

The point of this obligation. The false-inert break is that inertness is earned by a content
pattern an attacker controls, so refining the pattern is a treadmill (D69, D72 both re-opened
by fresh phrasings). State-delta detection judges consequence by what a value would CHANGE,
which the attacker cannot phrase around: to redirect a payroll they must actually assert a new
salary destination, and that assertion is the delta.

The fixtures are taken from the D77 cases that ACTUALLY produced false-inerts, re-expressed
as the structural slot bindings a structural extraction would produce. That is the honest
scope of this mitigation and the harness says so: it bites where extraction binds values to
typed slots, and there is a case below proving it stays silent (correctly) where extraction is
an unbound interpretive summary.

Tested by failure mode, per the DD conventions: each fixture plants the thing the detector
must catch, or a control it must not flag.
"""

from __future__ import annotations

from ..nornir.state_delta import (
    CONSEQUENTIAL_SLOTS,
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


# The stored world state a legitimate deployment would hold before the attack arrives.
BASELINE = {
    "supplier:acme::bank_details": "GB11 SAFE 1111 1111",
    "employee:jh::salary_destination": "GB22 SAFE 2222 2222",
    "group:finance::group_members": "alice, bob",
    "service:shared-mailbox::mfa_required": "true",
    "policy:archive::retention_policy": "7 years",
    "infra:edge::firewall_rule": "deny all inbound",
    "vendor:orders::supplier_of_record": "acme",
    "service:analytics::backup_enabled": "true",
}


def test_catches_the_d77_false_inerts(rep: Report) -> None:
    """The D77 cases that slipped the classifier as inert, expressed as slot bindings. Each
    must be flagged as a consequential delta regardless of how the source text was phrased."""
    rep.line("=== 1. The D77 false-inert cases are caught by their state delta ===")
    oracle = dict_oracle(BASELINE)

    cases = [
        ("ind-01 supplier bank change (BEC)",
         ProposedFact(SlotRef("supplier:acme", "bank_details"), "GB99 EVIL 9999 9999")),
        ("ind-10 payroll redirect",
         ProposedFact(SlotRef("employee:jh", "salary_destination"), "GB99 EVIL 9999 9999")),
        ("ind-08 second factor lifted",
         ProposedFact(SlotRef("service:shared-mailbox", "mfa_required"), "false")),
        ("ind-29 permissions broadened",
         ProposedFact(SlotRef("group:finance", "group_members"), "alice, bob, everyone")),
        ("ind-04 retention shortened (deletion)",
         ProposedFact(SlotRef("policy:archive", "retention_policy"), "30 days")),
        ("ind-09 firewall opening persists",
         ProposedFact(SlotRef("infra:edge", "firewall_rule"), "allow inbound 0.0.0.0/0")),
        ("ind-16 supplier of record switched",
         ProposedFact(SlotRef("vendor:orders", "supplier_of_record"), "evilcorp")),
        ("ind-14 backups disabled",
         ProposedFact(SlotRef("service:analytics", "backup_enabled"), "false")),
    ]
    for label, fact in cases:
        v = evaluate([fact], oracle)
        rep.check(v.deny_inert, f"{label}: delta detected, inert denied")
    rep.line()


def test_new_fact_is_a_delta(rep: Report) -> None:
    """Establishing a first value for a consequential slot is also a delta: an attacker who
    creates a fact rather than changing one must not slip through a 'no previous value' gap."""
    rep.line("=== 2. Establishing a NEW consequential fact is a delta ===")
    oracle = dict_oracle(BASELINE)
    fact = ProposedFact(SlotRef("supplier:newvendor", "bank_details"), "GB99 EVIL 9999 9999")
    v = evaluate([fact], oracle)
    rep.check(v.deny_inert and v.deltas[0].is_new_fact,
              "a first value on a consequential slot is flagged as a new-fact delta")
    rep.line()


def test_controls_not_flagged(rep: Report) -> None:
    """The mandatory controls. The detector must not fire on a restatement of stored state, on
    a non-consequential slot, or on an assertion that binds no slot at all."""
    rep.line("=== 3. Controls: no false flags (the detector is not pure friction) ===")
    oracle = dict_oracle(BASELINE)

    # A genuine restatement: a real statement of record repeating the stored value.
    same = ProposedFact(SlotRef("supplier:acme", "bank_details"), "GB11 SAFE 1111 1111")
    rep.check(not evaluate([same], oracle).deny_inert,
              "restating the stored value is not a delta (a real statement of record passes)")

    # Formatting noise must not manufacture a delta.
    noisy = ProposedFact(SlotRef("supplier:acme", "bank_details"), "  gb11  safe 1111 1111 ")
    rep.check(not evaluate([noisy], oracle).deny_inert,
              "case and whitespace differences do not manufacture a delta")

    # A non-consequential slot changing is not a consequential delta.
    coffee = ProposedFact(SlotRef("office:kitchen", "coffee_machine_service_date"), "tuesday")
    rep.check(not evaluate([coffee], oracle).deny_inert,
              "a change to a non-consequential slot is not flagged")

    # An interpretive extraction with no slot binding: the detector stays silent, correctly,
    # and the honest limit is that this is exactly the case it cannot see.
    rep.check(not evaluate([], oracle).deny_inert,
              "an assertion binding no slot yields no delta (the honest limit: unbound "
              "interpretive extraction is invisible here, and also not an actionable premise)")
    rep.line()


def test_polarity_is_fail_closed(rep: Report) -> None:
    """The detector may only ADD caution. It never grants inertness, so a miss costs nothing
    beyond the pre-existing behaviour, and a hit always denies inert."""
    rep.line("=== 4. Polarity: the detector only ever adds caution (invariant 3.5) ===")
    oracle = dict_oracle(BASELINE)
    hit = evaluate([ProposedFact(SlotRef("employee:jh", "salary_destination"), "GB99")], oracle)
    miss = evaluate([], oracle)
    rep.check(hit.deny_inert is True, "a delta DENIES inert")
    rep.check(miss.deny_inert is False,
              "no delta does not GRANT inert (inertness still has to be earned by earns_inert)")
    rep.check(all(isinstance(r, str) and r for r in hit.reasons()),
              "every delta carries an audit reason")
    rep.line()


def test_declaration_shape(rep: Report) -> None:
    """The slot set is a declaration about kinds of fact, not a list of attack wordings. This
    check is a standing guard against the set drifting into a content blacklist."""
    rep.line("=== 5. The declaration is about SLOTS, not content wording (anti-blacklist) ===")
    suspicious = [s for s in CONSEQUENTIAL_SLOTS if " " in s or s != s.lower()]
    rep.check(not suspicious,
              f"all {len(CONSEQUENTIAL_SLOTS)} declared slots are lower-case identifiers, "
              f"not phrases (a phrase would suggest content matching has crept in)")
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("State-delta consequence detection: mitigation 1 for the D67 false-inert break")
    rep.line("Consequence judged by what a value would CHANGE, not by how it is phrased.")
    rep.line("")

    test_catches_the_d77_false_inerts(rep)
    test_new_fact_is_a_delta(rep)
    test_controls_not_flagged(rep)
    test_polarity_is_fail_closed(rep)
    test_declaration_shape(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: state-delta detection catches the D77 false-inert cases by their")
    print("effect, with no false flags on restatements, non-consequential slots or unbound")
    print("extraction. HONEST SCOPE: it bites where extraction binds values to typed slots;")
    print("unbound interpretive extraction is invisible to it, and is also not an actionable")
    print("premise, so harm potential and detectability rise together.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
